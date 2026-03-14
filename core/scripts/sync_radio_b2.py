import os
import sys
import django
import requests
import base64
import urllib.parse

# Set up Django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')

# Manual .env loading
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

django.setup()

from core.models import RadioTrack, RadioStationState

# --- B2 CONFIGURATION ---
# Replace these with your actual B2 credentials or use environment variables
B2_KEY_ID = os.getenv('B2_KEY_ID', 'your_key_id')
B2_APPLICATION_KEY = os.getenv('B2_APPLICATION_KEY', 'your_application_key')
B2_BUCKET_NAME = os.getenv('B2_BUCKET_NAME', 'your_bucket_name')
B2_ENDPOINT = os.getenv('B2_ENDPOINT', '') # e.g. f000.backblazeb2.com

def get_b2_auth_token():
    """Authenticates with B2 and returns authorization details."""
    id_and_key = f"{B2_KEY_ID}:{B2_APPLICATION_KEY}"
    basic_auth_string = 'Basic ' + base64.b64encode(id_and_key.encode('ascii')).decode('ascii')
    headers = {'Authorization': basic_auth_string}
    
    response = requests.get('https://api.backblazeb2.com/b2api/v2/b2_authorize_account', headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to authorize with B2: {response.text}")
    
    data = response.json()
    return data['authorizationToken'], data['apiUrl'], data['accountId'], data['downloadUrl']

def list_b2_files(auth_token, api_url, bucket_id):
    """Lists all files in the given B2 bucket."""
    headers = {'Authorization': auth_token}
    post_params = {'bucketId': bucket_id}
    
    response = requests.post(f"{api_url}/b2api/v2/b2_list_file_names", json=post_params, headers=headers)
    if response.status_code != 200:
        raise Exception(f"Failed to list files: {response.text}")
    
    return response.json().get('files', [])

def sync_tracks_from_b2():
    print("Connecting to Backblaze B2...")
    if B2_KEY_ID == 'your_key_id':
        print("Please update B2_KEY_ID and B2_APPLICATION_KEY in the script or .env file.")
        return

    try:
        auth_token, api_url, account_id, download_url = get_b2_auth_token()
        
        # Get Bucket ID
        headers = {'Authorization': auth_token}
        bucket_response = requests.get(f"{api_url}/get_bucket_id?bucketName={B2_BUCKET_NAME}", headers=headers) # Note: endpoint might differ, using generic list buckets instead
        
        bucket_response = requests.get(f"{api_url}/b2api/v2/b2_list_buckets?accountId={account_id}", headers=headers)
        buckets = bucket_response.json().get('buckets', [])
        bucket = next((b for b in buckets if b['bucketName'] == B2_BUCKET_NAME), None)
        
        if not bucket:
            print(f"Bucket {B2_BUCKET_NAME} not found.")
            return

        files = list_b2_files(auth_token, api_url, bucket['bucketId'])
        
        print(f"Found {len(files)} files. Syncing database...")
        
        all_synced_ids = []
        for file in files:
            filename = file['fileName']
            print(f"Checking file: {filename}") # LOGGING
            if not filename.lower().endswith(('.mp3', '.wav', '.m4a')):
                print(f"Skipping {filename} - incorrect extension.")
                continue
                
            # Basic parsing of "Artist - Title.mp3"
            base_filename = filename.rsplit('.', 1)[0]
            title = base_filename
            artist = "Unknown Artist"
            if " - " in base_filename:
                parts = base_filename.split(' - ', 1)
                artist = parts[0]
                title = parts[1]
                
            # Construct Download URL (URL-encode the filename for special characters like #)
            safe_filename = urllib.parse.quote(filename)
            audio_url = f"{download_url}/file/{B2_BUCKET_NAME}/{safe_filename}"
            print(f"Syncing: {artist} - {title} URL: {audio_url}") # LOGGING
                
            # --- ALBUM ART MAPPING ---
            # Default fallback image (Stray Kids group photo)
            album_art = "https://res.cloudinary.com/diuanqnce/image/upload/v1710457000/ksync/skz_group_default.jpg"
            
            # Map common Stray Kids albums
            album_covers = {
                "5-STAR": "https://upload.wikimedia.org/wikipedia/en/3/30/Stray_Kids_-_5-Star.png",
                "ROCK-STAR": "https://upload.wikimedia.org/wikipedia/en/e/e0/Stray_Kids_-_Rock-Star.png",
                "NOEASY": "https://upload.wikimedia.org/wikipedia/en/b/b5/Stray_Kids_-_Noeasy.png",
                "ODDINARY": "https://upload.wikimedia.org/wikipedia/en/c/c8/Stray_Kids_-_Oddinary.png",
                "MAXIDENT": "https://upload.wikimedia.org/wikipedia/en/0/05/Stray_Kids_-_Maxident.png",
                "IN LIFE": "https://upload.wikimedia.org/wikipedia/en/f/f6/Stray_Kids_-_In_Life.png",
                "GO LIVE": "https://upload.wikimedia.org/wikipedia/en/8/8c/Stray_Kids_-_Go_Live.png",
                "CIRCUS": "https://upload.wikimedia.org/wikipedia/en/4/4b/Stray_Kids_-_Circus.png",
                "THE SOUND": "https://upload.wikimedia.org/wikipedia/en/2/2a/Stray_Kids_-_The_Sound.png",
                "SKZ-REPLAY": "https://upload.wikimedia.org/wikipedia/en/c/c2/SKZ-Replay_Cover.jpg",
                "ATE": "https://upload.wikimedia.org/wikipedia/en/6/6f/Stray_Kids_-_Ate.png",
            }
            
            # Try to match title or artist to an album
            upper_title = title.upper()
            for album, url in album_covers.items():
                if album in upper_title:
                    album_art = url
                    break
            
            track, created = RadioTrack.objects.update_or_create(
                title=title,
                artist=artist,
                defaults={
                    'audio_url': audio_url,
                    'album_art': album_art,
                    'duration': '3:00', # Default duration
                }
            )
            all_synced_ids.append(track.id)
            if created:
                print(f"Added new track: {track.title}")
            else:
                print(f"Updated track: {track.title}")

        # --- AUTO-DJ ROTATION LOGIC ---
        state, _ = RadioStationState.objects.get_or_create(id=1)
        
        if all_synced_ids:
            # If no current track, pick the first one
            if not state.current_track:
                state.current_track_id = all_synced_ids[0]
                print(f"Set current track to: {state.current_track.title}")
            
            # Simple queue generation (randomized or sequential)
            import random
            shuffled = list(all_synced_ids)
            random.shuffle(shuffled)
            
            # Filter out current track from queue
            queue_ids = [tid for tid in shuffled if tid != state.current_track_id][:5]
            state.up_next = queue_ids
            
            # If history is empty, pick some random ones
            if not state.recently_played:
                state.recently_played = [tid for tid in shuffled if tid not in queue_ids and tid != state.current_track_id][:3]
            
            state.save()
            print(f"Radio state updated. Queue contains {len(state.up_next)} tracks.")

        print("Sync complete.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    sync_tracks_from_b2()
