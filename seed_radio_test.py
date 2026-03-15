import os
import django
from django.utils import timezone
from datetime import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import RadioTrack, RadioPlaylist, RadioPlaylistTrack, RadioSchedule

def seed_test_data():
    print("Seeding test data...")
    
    # 1. Get or create some tracks
    track1, _ = RadioTrack.objects.get_or_create(title="Seven", artist="Jung Kook", duration="3:45")
    track2, _ = RadioTrack.objects.get_or_create(title="Dynamite", artist="BTS", duration="3:19")
    track3, _ = RadioTrack.objects.get_or_create(title="Super Shy", artist="NewJeans", duration="2:34")
    
    # 2. Create a Playlist
    playlist, _ = RadioPlaylist.objects.get_or_create(name="Morning K-Pop Hits", description="The best way to start your day.")
    
    # 3. Add tracks to playlist if not already there
    RadioPlaylistTrack.objects.get_or_create(playlist=playlist, track=track1, order=1)
    RadioPlaylistTrack.objects.get_or_create(playlist=playlist, track=track2, order=2)
    RadioPlaylistTrack.objects.get_or_create(playlist=playlist, track=track3, order=3)
    
    # 4. Schedule the playlist for TODAY
    now = timezone.now()
    # Get current day in MON-SUN format
    days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    # weekday() returns 0 for Monday, 6 for Sunday
    today_code = days[now.weekday()]
    
    # Clear existing schedule for today to avoid clutter
    RadioSchedule.objects.filter(day=today_code).delete()
    
    # Create a schedule that is ACTIVE NOW
    current_hour = now.hour
    start_time = time(current_hour, 0)
    end_time = time((current_hour + 2) % 24, 0)
    
    RadioSchedule.objects.create(
        day=today_code,
        start_time=start_time,
        end_time=end_time,
        playlist=playlist,
        host="DJ Gemini",
        genre="LIVE",
        description="Fresh hits and interactive chat."
    )
    
    # Create an upcoming schedule
    upcoming_start = time((current_hour + 2) % 24, 0)
    upcoming_end = time((current_hour + 4) % 24, 0)
    
    RadioSchedule.objects.create(
        day=today_code,
        start_time=upcoming_start,
        end_time=upcoming_end,
        playlist=playlist,
        host="Auto DJ",
        genre="MUSIC",
        description="Non-stop music through the afternoon."
    )
    
    print(f"Successfully created schedule for {today_code} starting at {start_time}")

if __name__ == "__main__":
    seed_test_data()
