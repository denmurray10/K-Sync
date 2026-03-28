import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import RadioTrack, KPopGroup, KPopMember
from django.db.models import Q

print("================ DIAGNOSTICS ================")

# 1. RadioTracks without proper audio_url
bad_tracks = RadioTrack.objects.filter(
    Q(audio_url__isnull=True) | 
    Q(audio_url__exact='') | 
    Q(audio_url__exact='None')
)
invalid_urls = RadioTrack.objects.exclude(
    Q(audio_url__isnull=True) | 
    Q(audio_url__exact='') | 
    Q(audio_url__exact='None')
).exclude(audio_url__startswith='http')

print(f"Total RadioTracks without audio_url: {bad_tracks.count()} / {RadioTrack.objects.count()}")
for track in bad_tracks[:5]:
    print(f" - [ID {track.id}] {track.artist} - {track.title}")

print(f"\nRadioTracks with invalid URL format (not starting with http): {invalid_urls.count()}")
for track in invalid_urls[:5]:
    print(f" - [ID {track.id}] {track.artist} - {track.title} -> URL: {track.audio_url}")

# 2. Check Groups without images
bad_groups = KPopGroup.objects.filter(Q(image_url__isnull=True) | Q(image_url__exact='') | Q(image_url__exact='None'))
print(f"\nTotal KPopGroups without image_url: {bad_groups.count()} / {KPopGroup.objects.count()}")
for group in bad_groups[:5]:
    print(f" - [ID {group.id}] {group.name}")

# 3. Check Members without images
bad_members = KPopMember.objects.filter(Q(image_url__isnull=True) | Q(image_url__exact='') | Q(image_url__exact='None'))
print(f"\nTotal KPopMembers without image_url: {bad_members.count()} / {KPopMember.objects.count()}")
for member in bad_members[:5]:
    print(f" - [ID {member.id}] {member.name} (from {member.group.name})")

print("================ DONE ================")
