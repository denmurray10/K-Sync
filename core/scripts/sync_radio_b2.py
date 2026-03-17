import os
import sys
import django
import requests
import base64
import urllib.parse
import argparse

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

import io
import cloudinary
import cloudinary.uploader
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC
from django.conf import settings

# Configure Cloudinary
cloudinary.config(
    cloud_name=getattr(settings, 'CLOUDINARY_CLOUD_NAME', ''),
    api_key=getattr(settings, 'CLOUDINARY_API_KEY', ''),
    api_secret=getattr(settings, 'CLOUDINARY_API_SECRET', ''),
    secure=True,
)

def extract_metadata(audio_url, track_id):
    """
    Attempts to download the beginning of the file to extract ID3 artwork and artist,
    then uploads artwork to Cloudinary.
    """
    metadata = {
        'album_art': None,
        'artist': None,
        'duration_seconds': 0,
        'duration_str': "3:00"
    }
    try:
        # Download first 1MB (art and metadata are usually at the start)
        headers = {'Range': 'bytes=0-1048576'}
        response = requests.get(audio_url, headers=headers, timeout=10)
        if response.status_code not in [200, 206]:
            return metadata
            
        file_data = io.BytesIO(response.content)
        
        # Extract Duration
        try:
            audio_info = MP3(file_data).info
            seconds = int(audio_info.length)
            metadata['duration_seconds'] = seconds
            mins, secs = divmod(seconds, 60)
            metadata['duration_str'] = f"{mins}:{secs:02d}"
        except Exception as e:
            print(f"Duration extraction failed: {e}")

        try:
            file_data.seek(0)
            tags = ID3(file_data)
        except Exception:
            return metadata
            
        # Extract Artist (TPE1 is the official tag for Lead Artist)
        if 'TPE1' in tags:
            metadata['artist'] = str(tags['TPE1'])
            print(f"    Found Artist: {metadata['artist']}")
        elif 'TPE2' in tags:
            metadata['artist'] = str(tags['TPE2'])
            print(f"    Found Artist: {metadata['artist']}")

        # Extract Artwork
        for tag in tags.values():
            if isinstance(tag, APIC):
                try:
                    upload_result = cloudinary.uploader.upload(
                        tag.data,
                        folder="radio/album_art",
                        public_id=f"track_{track_id}",
                        overwrite=True,
                        resource_type='image'
                    )
                    metadata['album_art'] = upload_result.get('secure_url')
                except Exception as upload_err:
                    print(f"Cloudinary upload error: {upload_err}")
                break
    except Exception as e:
        print(f"Metadata extraction error: {e}")
    return metadata

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

def sync_tracks_from_b2(prune_missing=False, new_only=False):
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
        all_synced_urls = set()
        created_count = 0
        updated_count = 0
        skipped_existing_count = 0

        existing_titles = set()
        if new_only:
            existing_titles = {
                (t or '').strip().lower()
                for t in RadioTrack.objects.values_list('title', flat=True)
                if t
            }

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

            all_synced_urls.add(audio_url)

            normalized_title = (title or '').strip().lower()
            if new_only and normalized_title in existing_titles:
                skipped_existing_count += 1
                print(f"Skipping existing track (new-only mode): {title}")
                continue
                
            # --- EMBEDDED METADATA EXTRACTION ---
            # Attempt to extract art and artist from the file on B2
            metadata = extract_metadata(audio_url, safe_filename.replace('%', '_'))
            album_art = metadata.get('album_art')
            extracted_artist = metadata.get('artist')
            
            # Use extracted artist if found, otherwise keep title-parsed artist
            if extracted_artist:
                artist = extracted_artist
            
            # Default fallback if extraction fails
            if not album_art:
                 album_art = "https://res.cloudinary.com/diuanqnce/image/upload/v1710546648/ksync/skz_group_default.jpg"
            
            defaults = {
                'artist': artist,
                'audio_url': audio_url,
                'album_art': album_art,
                'duration': metadata.get('duration_str', '3:00'),
                'duration_seconds': metadata.get('duration_seconds', 180),
            }
            existing_matches = RadioTrack.objects.filter(title=title).order_by('id')
            track = existing_matches.first()
            if track:
                for field_name, field_value in defaults.items():
                    setattr(track, field_name, field_value)
                track.save(update_fields=list(defaults.keys()))
                created = False
            else:
                track = RadioTrack.objects.create(title=title, **defaults)
                created = True
            all_synced_ids.append(track.id)
            if created:
                created_count += 1
                print(f"Added new track: {track.title}")
            else:
                updated_count += 1
                print(f"Updated track: {track.title}")

        deleted_count = 0
        if prune_missing:
            b2_url_fragment = f"/file/{B2_BUCKET_NAME}/"
            stale_tracks = RadioTrack.objects.filter(audio_url__contains=b2_url_fragment).exclude(audio_url__in=all_synced_urls)
            stale_count = stale_tracks.count()
            if stale_count:
                print(f"Removing {stale_count} track(s) no longer present in B2...")
                deleted_count, _ = stale_tracks.delete()
            else:
                print("No stale B2 tracks to remove.")

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
        print(
            f"Summary: created={created_count}, updated={updated_count}, "
            f"skipped_existing={skipped_existing_count}, deleted={deleted_count}"
        )
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync radio tracks from Backblaze B2")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete DB tracks whose B2 files no longer exist",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only add tracks that are not already in DB by title (skip updates)",
    )
    args = parser.parse_args()

    sync_tracks_from_b2(prune_missing=args.prune, new_only=args.new_only)
