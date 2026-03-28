"""
Fast diagnostic + fix script for K-Sync data issues.
Run: python fix_data.py
"""
import os, json, sys, urllib.request, urllib.parse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')

import django
django.setup()

from django.db.models import Q
from core.models import RadioTrack, KPopGroup, KPopMember

# ─── 1. TRACK DIAGNOSTICS ─────────────────────────────────────────────────────
print("=" * 60)
print("TRACK DIAGNOSTICS")
print("=" * 60)

total = RadioTrack.objects.count()
no_audio = RadioTrack.objects.filter(Q(audio_url__isnull=True) | Q(audio_url='')).count()
no_art = RadioTrack.objects.filter(Q(album_art__isnull=True) | Q(album_art='') | Q(album_art__contains='about_banner')).count()
zero_dur = RadioTrack.objects.filter(duration_seconds__lte=0).count()

print(f"Total tracks: {total}")
print(f"Missing audio_url: {no_audio}")
print(f"Missing/placeholder album_art: {no_art}")
print(f"Zero duration: {zero_dur}")

# Check for swapped title/artist (artist field contains known group names as title)
KNOWN_GROUPS = ['BTS', 'BLACKPINK', 'SEVENTEEN', 'Stray Kids', 'TWICE', 'EXO', 'NCT', 'aespa', 'IVE', 'ITZY', 'ATEEZ', 'ENHYPEN', 'Red Velvet', 'MONSTA X', 'GOT7', 'MAMAMOO']
swapped = []
for t in RadioTrack.objects.all().only('id', 'title', 'artist', 'duration_seconds', 'album_art', 'audio_url'):
    title_upper = (t.title or '').strip().upper()
    for gname in KNOWN_GROUPS:
        if title_upper == gname.upper() and (t.artist or '').strip().upper() != gname.upper():
            swapped.append(t)
            break

print(f"\nPossible SWAPPED title/artist: {len(swapped)}")
for t in swapped[:15]:
    print(f"  [ID {t.id}] title='{t.title}' artist='{t.artist}' dur={t.duration_seconds}s art={'YES' if t.album_art and 'about_banner' not in t.album_art else 'PLACEHOLDER'}")

# ─── 2. MEMBER IMAGE DIAGNOSTICS ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("MEMBER IMAGE DIAGNOSTICS")
print("=" * 60)

total_members = KPopMember.objects.count()
no_img = KPopMember.objects.filter(Q(image_url__isnull=True) | Q(image_url='')).count()
print(f"Total members: {total_members}")
print(f"Missing image_url: {no_img}")

# Show members missing images grouped by group
missing = KPopMember.objects.filter(
    Q(image_url__isnull=True) | Q(image_url='')
).select_related('group').order_by('group__rank', 'group__name', 'order')

groups_affected = {}
for m in missing:
    gname = m.group.name
    if gname not in groups_affected:
        groups_affected[gname] = []
    groups_affected[gname].append(m.stage_name or m.name)

print(f"Groups with missing member images: {len(groups_affected)}")
for gname, members in list(groups_affected.items())[:10]:
    print(f"  {gname}: {', '.join(members)}")

# ─── 3. GROUP IMAGE DIAGNOSTICS ───────────────────────────────────────────────
print("\n" + "=" * 60)
print("GROUP IMAGE DIAGNOSTICS")
print("=" * 60)

total_groups = KPopGroup.objects.count()
no_group_img = KPopGroup.objects.filter(Q(image_url__isnull=True) | Q(image_url='')).count()
print(f"Total groups: {total_groups}")
print(f"Missing image_url: {no_group_img}")

for g in KPopGroup.objects.filter(Q(image_url__isnull=True) | Q(image_url='')).order_by('rank')[:10]:
    print(f"  [Rank {g.rank}] {g.name}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
