import re
import json
import urllib.request
import urllib.parse
from django.core.management.base import BaseCommand
from django.db.models import Q
from core.models import KPopGroup, KPopMember


GROUP_NAME_MAP = {
    '(G)I-DLE': 'i-dle',
    'BLACKPINK': 'BLACKPINK',
    'BTS': 'BTS',
    'SEVENTEEN': 'SEVENTEEN',
    'Stray Kids': 'Stray-Kids',
    'EXO': 'EXO',
    'TWICE': 'TWICE',
    'SHINee': 'SHINee',
    'NCT 127': 'NCT-127',
    'NCT Dream': 'NCT-Dream',
    'Super Junior': 'Super-Junior',
    'ATEEZ': 'ATEEZ',
    'ENHYPEN': 'ENHYPEN',
    'TXT (Tomorrow X Together)': 'TXT',
    'aespa': 'aespa',
    'IVE': 'IVE',
    'LE SSERAFIM': 'LE-SSERAFIM',
    'NewJeans': 'NewJeans',
    'ITZY': 'ITZY',
    'TREASURE': 'TREASURE',
    'ZEROBASEONE': 'ZEROBASEONE',
    'RIIZE': 'RIIZE',
    'TWS': 'TWS',
    'GOT7': 'GOT7',
    'MONSTA X': 'MONSTA-X',
    'Red Velvet': 'Red-Velvet',
    'NCT U': 'NCT-U',
    'BIGBANG': 'BIGBANG',
    "Girls' Generation (SNSD)": 'Girls-Generation',
    'MAMAMOO': 'MAMAMOO',
    'BABYMONSTER': 'BABYMONSTER',
    'ILLIT': 'ILLIT',
    'ASTRO': 'ASTRO',
    'IZ*ONE': 'IZ-ONE',
    'EXID': 'EXID',
    'Wanna One': 'Wanna-One',
    'CIX': 'CIX',
    'DAY6': 'DAY6',
    'HIGHLIGHT': 'Highlight',
    'VICTON': 'VICTON',
    'KISS OF LIFE': 'KISS-OF-LIFE',
    'fromis_9': 'fromis-9',
    'VERIVERY': 'VERIVERY',
    'PENTAGON': 'PENTAGON',
    'THE BOYZ': 'THE-BOYZ',
    'EVNNE': 'EVNNE',
    'FIFTY FIFTY': 'FIFTY-FIFTY',
    'STAYC': 'STAYC',
    'Kep1er': 'Kep1er',
    'XODIAC': 'XODIAC',
}

MEMBER_NAME_MAP = {
    'Rosé': 'Rose',
    'j-hope': 'j-hope',
    'SUGA': 'Suga',
    'RM': 'RM',
    'Jimin': 'Jimin2',
    'Bang Chan': 'Bang-Chan',
    'Lee Know': 'Lee-Know',
    'Hyunjin': 'Hyunjin2',
    'Seungmin': 'Seungmin2',
    'I.N': 'I-N',
    'D.O.': 'D-O',
    'S.Coups': 'S-Coups',
    'The8': 'The8',
    'Huening Kai': 'Huening-Kai',
    'Ni-ki': 'Ni-ki',
    'BamBam': 'BamBam',
    'JB': 'Jay-B',
    'Yunjin': 'Huh-Yunjin',
    'Leeseo': 'Leeseo',
    'Haechan': 'Haechan',
    'Karina': 'Karina2',
    'Giselle': 'giselle',
    'Winter': 'winter',
    'Ningning': 'ningning',
}


def _normalize(name: str) -> str:
    return re.sub(r'\s+', '-', str(name).strip()).replace('_', '-')


def _name_candidates(name: str, mapping: dict):
    mapped = mapping.get(name)
    candidates = []
    if mapped:
        candidates.append(mapped)
    candidates.extend([
        _normalize(name),
        _normalize(name).upper(),
        _normalize(name).title(),
    ])
    seen = set()
    out = []
    for value in candidates:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _verify_image(url: str) -> bool:
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://kpopping.com/',
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content_type = (resp.headers.get('Content-Type') or '').lower()
            return 'image' in content_type
    except Exception:
        return False


def _find_kpopping_profile_image(name: str, preferred_folder: str = '') -> str:
    folders = ('groups', 'idols')
    if preferred_folder == 'groups':
        folders = ('groups', 'idols')
    elif preferred_folder == 'idols':
        folders = ('idols', 'groups')
    exts = ('webp', 'jpg', 'jpeg', 'png')

    mapping = GROUP_NAME_MAP if preferred_folder != 'idols' else MEMBER_NAME_MAP
    for candidate in _name_candidates(name, mapping):
        encoded = urllib.parse.quote(candidate, safe='-')
        for folder in folders:
            for ext in exts:
                url = f'https://cdn.kpopping.com/{folder}/{encoded}/profile.{ext}'
                if _verify_image(url):
                    return url
    return ''


def _fetch_kpopping_group_payload(name: str):
    for candidate in _name_candidates(name, GROUP_NAME_MAP):
        encoded = urllib.parse.quote(candidate, safe='-')
        url = f'https://kpopping.com/api/groups/{encoded}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://kpopping.com/',
            'Accept': 'application/json',
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                payload = json.loads(raw)
                if isinstance(payload, dict) and isinstance(payload.get('members'), list):
                    return payload
        except Exception:
            continue
    return None


def _backfill_missing_members(*, top50: bool, dry_run: bool, style, stdout):
    qs = KPopGroup.objects.all()
    if top50:
        qs = qs.filter(rank__isnull=False)

    groups = list(qs.order_by('rank', 'name'))
    groups_without_members = [g for g in groups if not g.members.exists()]
    if not groups_without_members:
        stdout.write(style.SUCCESS('No groups are missing members.'))
        return 0, 0

    created = 0
    failed_groups = 0
    stdout.write(f'Backfilling members for {len(groups_without_members)} group(s) with no members...')

    for group in groups_without_members:
        payload = _fetch_kpopping_group_payload(group.name)
        members = (payload or {}).get('members') if payload else None
        if not members:
            failed_groups += 1
            stdout.write(style.WARNING(f'FAIL  [BACKFILL] {group.name}'))
            continue

        for index, member in enumerate(members, start=1):
            stage_name = str(member.get('name') or '').strip()
            if not stage_name:
                continue
            image_url = str(member.get('image') or '').strip()
            position = str(member.get('position') or '').strip()

            defaults = {
                'name': stage_name,
                'stage_name': stage_name,
                'position': position,
                'order': index,
            }
            if image_url:
                defaults['image_url'] = image_url

            if not dry_run:
                KPopMember.objects.update_or_create(
                    group=group,
                    stage_name=stage_name,
                    defaults=defaults,
                )
            created += 1

        stdout.write(style.SUCCESS(f'OK    [BACKFILL] {group.name} (+{len(members)} member(s))'))

    return created, failed_groups


def _sync_groups(*, top50: bool, only_missing: bool, dry_run: bool, style, stdout):
    qs = KPopGroup.objects.all()
    if top50:
        qs = qs.filter(rank__isnull=False)
    if only_missing:
        qs = qs.filter(Q(image_url__isnull=True) | Q(image_url=''))

    groups = list(qs.order_by('rank', 'name'))
    if not groups:
        stdout.write(style.WARNING('No groups matched the selected filters.'))
        return 0, 0, 0

    updated = 0
    skipped = 0
    failed = 0

    stdout.write(f'Processing {len(groups)} group(s)...')
    for group in groups:
        found = _find_kpopping_profile_image(group.name, preferred_folder='groups')
        if not found:
            failed += 1
            stdout.write(style.WARNING(f'FAIL  [GROUP] {group.name}'))
            continue

        if (group.image_url or '').strip() == found:
            skipped += 1
            stdout.write(f'SKIP  [GROUP] {group.name}')
            continue

        if not dry_run:
            group.image_url = found
            group.save(update_fields=['image_url'])

        updated += 1
        stdout.write(style.SUCCESS(f'OK    [GROUP] {group.name} -> {found}'))

    return updated, skipped, failed


def _sync_members(*, top50: bool, only_missing: bool, dry_run: bool, style, stdout):
    qs = KPopMember.objects.select_related('group').all()
    if top50:
        qs = qs.filter(group__rank__isnull=False)
    if only_missing:
        qs = qs.filter(Q(image_url__isnull=True) | Q(image_url=''))

    members = list(qs.order_by('group__rank', 'group__name', 'order', 'name'))
    if not members:
        stdout.write(style.WARNING('No members matched the selected filters.'))
        return 0, 0, 0

    updated = 0
    skipped = 0
    failed = 0

    stdout.write(f'Processing {len(members)} member(s)...')
    for member in members:
        stage = (member.stage_name or member.name or '').strip()
        if not stage:
            failed += 1
            stdout.write(style.WARNING(f'FAIL  [MEMBER] {member.group.name}/(no-name)'))
            continue

        found = _find_kpopping_profile_image(stage, preferred_folder='idols')
        if not found:
            failed += 1
            stdout.write(style.WARNING(f'FAIL  [MEMBER] {member.group.name}/{stage}'))
            continue

        if (member.image_url or '').strip() == found:
            skipped += 1
            stdout.write(f'SKIP  [MEMBER] {member.group.name}/{stage}')
            continue

        if not dry_run:
            member.image_url = found
            member.save(update_fields=['image_url'])

        updated += 1
        stdout.write(style.SUCCESS(f'OK    [MEMBER] {member.group.name}/{stage} -> {found}'))

    return updated, skipped, failed


class Command(BaseCommand):
    help = 'Sync Kpopping profile images for groups and members.'

    def add_arguments(self, parser):
        parser.add_argument('--top50', action='store_true', help='Only process ranked top-50 groups (rank not null).')
        parser.add_argument('--only-missing', action='store_true', help='Only process records with empty image_url.')
        parser.add_argument('--groups-only', action='store_true', help='Sync only group photos.')
        parser.add_argument('--members-only', action='store_true', help='Sync only member photos.')
        parser.add_argument('--backfill-members', action='store_true', help='Create missing member records from Kpopping group API before image sync.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without writing.')

    def handle(self, *args, **options):
        if options['groups_only'] and options['members_only']:
            self.stdout.write(self.style.ERROR('Use either --groups-only or --members-only, not both.'))
            return

        run_groups = not options['members_only']
        run_members = not options['groups_only']

        total_updated = 0
        total_skipped = 0
        total_failed = 0

        if options['backfill_members']:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('=== MEMBER BACKFILL ==='))
            created, failed_groups = _backfill_missing_members(
                top50=options['top50'],
                dry_run=options['dry_run'],
                style=self.style,
                stdout=self.stdout,
            )
            self.stdout.write(self.style.SUCCESS(f'Backfilled members: {created}'))
            self.stdout.write(self.style.WARNING(f'Backfill group failures: {failed_groups}'))

        if run_groups:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('=== GROUP PHOTOS ==='))
            updated, skipped, failed = _sync_groups(
                top50=options['top50'],
                only_missing=options['only_missing'],
                dry_run=options['dry_run'],
                style=self.style,
                stdout=self.stdout,
            )
            total_updated += updated
            total_skipped += skipped
            total_failed += failed

        if run_members:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE('=== MEMBER PHOTOS ==='))
            updated, skipped, failed = _sync_members(
                top50=options['top50'],
                only_missing=options['only_missing'],
                dry_run=options['dry_run'],
                style=self.style,
                stdout=self.stdout,
            )
            total_updated += updated
            total_skipped += skipped
            total_failed += failed

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Updated: {total_updated}'))
        self.stdout.write(f'Skipped: {total_skipped}')
        self.stdout.write(self.style.WARNING(f'Failed: {total_failed}'))
