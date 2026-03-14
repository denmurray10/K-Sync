import os
import sys
import django

# Set up Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import RadioTrack, RadioStationState

def fix_db():
    print("Deleting tracks with no audio URL...")
    deleted_count, _ = RadioTrack.objects.filter(audio_url__isnull=True).delete()
    deleted_count_empty, _ = RadioTrack.objects.filter(audio_url="").delete()
    print(f"Deleted {deleted_count + deleted_count_empty} invalid tracks.")
    
    print("Clearing Station State...")
    RadioStationState.objects.all().delete()
    print("Station state cleared. Ready for re-sync.")

if __name__ == "__main__":
    fix_db()
