import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import RadioTrack, RadioStationState

def check_data():
    print("Listing all RadioTrack records:")
    tracks = RadioTrack.objects.all()
    for t in tracks:
        print(f"ID: {t.id} | {t.artist} - {t.title} | ART: '{t.album_art}'")
    
    state = RadioStationState.objects.first()
    if state:
        print(f"\nStation State (ID: {state.id}):")
        print(f"  Current Track ID: {state.current_track_id}")

    print("\nUp Next IDs:", state.up_next)
    for tid in state.up_next:
        t = RadioTrack.objects.filter(id=tid).first()
        if t:
            print(f"  Track {tid}: {t.title} - URL: '{t.audio_url}'")
        else:
            print(f"  Track {tid}: NOT FOUND")

if __name__ == "__main__":
    check_data()
