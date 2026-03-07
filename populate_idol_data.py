"""
populate_idol_data.py
─────────────────────
One-time script to enrich all KPopGroup records with:
  • AI-generated description (DeepSeek)
  • Member list  (DeepSeek)
  • Image URL    (iTunes Search API — free, no scraping)

Run:  python populate_idol_data.py

Safe to re-run — skips groups that already have a description.
Use --force to overwrite everything.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse

# ── Django setup ──────────────────────────────────────────────────────────────
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
import django
django.setup()

from django.conf import settings
from core.models import KPopGroup, KPopMember

DEEPSEEK_API_KEY = getattr(settings, 'DEEPSEEK_API_KEY', '')
FORCE = '--force' in sys.argv

# ── Helpers ───────────────────────────────────────────────────────────────────

def deepseek_chat(prompt: str, retries: int = 3) -> str:
    """Call DeepSeek chat endpoint, return assistant message text."""
    url = 'https://api.deepseek.com/chat/completions'
    payload = json.dumps({
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.7,
        'max_tokens': 1024,
    }).encode()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
    }
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f'  DeepSeek attempt {attempt} failed: {e}')
            if attempt < retries:
                time.sleep(2 ** attempt)
    return ''


def itunes_artist_image(artist_name: str) -> str:
    """Return the best available artist/album image URL from iTunes Search API."""
    query = urllib.parse.quote(artist_name)
    # First try: artist lookup
    url = f'https://itunes.apple.com/search?term={query}&entity=musicArtist&limit=1'
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            results = data.get('results', [])
            if results and results[0].get('artworkUrl100'):
                # Scale up to 600x600
                return results[0]['artworkUrl100'].replace('100x100', '600x600')
    except Exception:
        pass
    # Fallback: search an album by this artist
    url2 = f'https://itunes.apple.com/search?term={query}&entity=album&limit=1&country=KR'
    try:
        with urllib.request.urlopen(url2, timeout=10) as resp:
            data = json.loads(resp.read())
            results = data.get('results', [])
            if results and results[0].get('artworkUrl100'):
                return results[0]['artworkUrl100'].replace('100x100', '600x600')
    except Exception:
        pass
    return ''


def parse_members_json(text: str) -> list:
    """Extract JSON array from DeepSeek response."""
    # Strip markdown code fences if present
    text = text.strip()
    if '```' in text:
        start = text.find('[')
        end = text.rfind(']') + 1
        text = text[start:end]
    try:
        return json.loads(text)
    except Exception:
        # Try to find the array manually
        start = text.find('[')
        end = text.rfind(']') + 1
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
    return []


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    groups = KPopGroup.objects.all().order_by('rank')
    print(f'Found {groups.count()} groups.\n')

    for group in groups:
        has_desc = bool(group.description)
        has_members = group.members.exists()
        has_image = bool(group.image_url)

        if has_desc and has_members and has_image and not FORCE:
            print(f'[SKIP] {group.name} — already populated')
            continue

        print(f'[{group.rank}] Processing {group.name} ({group.group_type})...')

        # ── 1. Description ────────────────────────────────────────────────────
        if not has_desc or FORCE:
            prompt = (
                f'Write a compelling 3-sentence bio for the K-Pop {group.get_group_type_display()} '
                f'"{group.name}" signed to {group.label}. '
                f'Focus on their musical style, achievements, and what makes them unique. '
                f'Write in present tense, energetic tone. Plain text only, no markdown.'
            )
            desc = deepseek_chat(prompt)
            if desc:
                group.description = desc
                print(f'  ✓ Description ({len(desc)} chars)')
            else:
                print(f'  ✗ Description failed')
            time.sleep(0.5)

        # ── 2. Members ────────────────────────────────────────────────────────
        if not has_members or FORCE:
            if group.group_type == 'SOLO':
                # Solo artists have no members to list, just themselves
                members_data = [{'name': group.name, 'stage_name': group.name, 'position': 'Solo Artist'}]
            else:
                prompt = (
                    f'List all members of the K-Pop group "{group.name}". '
                    f'Return ONLY a JSON array. Each element must have: '
                    f'"name" (full Korean name in English), "stage_name" (stage name), "position" (e.g. Vocalist, Rapper, Dancer, Leader, Maknae). '
                    f'Example: [{{"name": "Kim Jisoo", "stage_name": "Jisoo", "position": "Vocalist, Visual"}}]. '
                    f'Return only the JSON array, nothing else.'
                )
                raw = deepseek_chat(prompt)
                members_data = parse_members_json(raw)
                time.sleep(0.5)

            if members_data:
                if FORCE:
                    group.members.all().delete()
                for i, m in enumerate(members_data):
                    KPopMember.objects.get_or_create(
                        group=group,
                        name=m.get('name', m.get('stage_name', '')),
                        defaults={
                            'stage_name': m.get('stage_name', ''),
                            'position': m.get('position', ''),
                            'order': i,
                        }
                    )
                print(f'  ✓ Members: {len(members_data)} saved')
            else:
                print(f'  ✗ Members parse failed — raw: {raw[:80] if "raw" in dir() else "n/a"}')

        # ── 3. iTunes image ───────────────────────────────────────────────────
        if not has_image or FORCE:
            img = itunes_artist_image(group.name)
            if img:
                group.image_url = img
                print(f'  ✓ Image: {img[:60]}...')
            else:
                print(f'  ✗ No iTunes image found')
            time.sleep(0.3)

        group.save()
        print()

    print('Done.')


if __name__ == '__main__':
    main()
