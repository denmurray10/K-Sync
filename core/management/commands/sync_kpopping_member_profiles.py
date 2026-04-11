import json
import re
import urllib.parse
import urllib.request
from html import unescape
from datetime import datetime

from django.core.management.base import BaseCommand

from core.models import KPopMember


MEMBER_NAME_MAP = {
    'Rosé': 'Rose',
    'RosÃ©': 'Rose',
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


def _normalize(name):
    return re.sub(r'\s+', '-', str(name or '').strip()).replace('_', '-')


def _name_candidates(name):
    mapped = MEMBER_NAME_MAP.get(name)
    candidates = []
    if mapped:
        candidates.append(mapped)
    candidates.extend([
        _normalize(name),
        _normalize(name).title(),
        _normalize(name).upper(),
    ])
    seen = set()
    out = []
    for value in candidates:
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(value)
    return out


def _http_get(url):
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://kpopping.com/',
            'Accept': 'application/json,text/html;q=0.9,*/*;q=0.8',
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode('utf-8', errors='ignore')


def _clean_text(value):
    text = str(value or '').strip()
    if not text:
        return ''
    try:
        text = text.encode('latin1', errors='ignore').decode('utf-8', errors='ignore')
    except Exception:
        pass
    text = unescape(text)
    text = re.sub(r'\bi n\b', 'in', text)
    text = re.sub(r'\s+([,.;:!?])', r'\1', text)
    text = re.sub(r'([(\["])\s+', r'\1', text)
    text = re.sub(r'\s+([)\]"])', r'\1', text)
    text = text.replace('kpop', 'K-pop')
    return re.sub(r'\s+', ' ', text).strip()


def _clean_multiline_text(value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    parts = [_clean_text(chunk) for chunk in re.split(r'\n\s*\n+', raw) if _clean_text(chunk)]
    return '\n\n'.join(parts)


def _strip_tags(value):
    text = re.sub(r'<br\s*/?>', '\n', value, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    return _clean_text(text)


def _profile_text_lines(html):
    main = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
    main = re.sub(r'<br\s*/?>', '\n', main, flags=re.IGNORECASE)
    main = re.sub(r'</(p|div|li|h1|h2|h3|h4|tr)>', '\n', main, flags=re.IGNORECASE)
    main = re.sub(r'<[^>]+>', ' ', main)
    main = unescape(main)
    return [re.sub(r'\s+', ' ', line).strip() for line in main.splitlines() if re.sub(r'\s+', ' ', line).strip()]


def _extract_label(lines, label):
    prefix = f'{label}:'
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ''


def _extract_facts(lines, stage_name):
    heading = f'{stage_name} Facts:'
    facts = []
    collecting = False
    for line in lines:
        if line == heading:
            collecting = True
            continue
        if collecting:
            if line.startswith('Note:') or line.startswith('Back to:') or line.startswith('Do you like'):
                break
            if line.startswith('- ') or line.startswith('– '):
                facts.append(line.lstrip('-– ').strip())
    return facts


def _extract_socials(lines):
    socials = []
    for label in ('Instagram', 'Spotify', 'YouTube', 'TikTok', 'Weibo'):
        value = _extract_label(lines, label)
        if value:
            socials.append({'label': label, 'url': value})
    return socials


def _iso_to_date(value):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], '%Y-%m-%d').date()
    except ValueError:
        return None


def _country_name(value):
    code = str(value or '').strip().upper()
    if code == 'KR':
        return 'South Korean'
    if code == 'TH':
        return 'Thai'
    if code == 'JP':
        return 'Japanese'
    if code == 'CN':
        return 'Chinese'
    if code == 'NZ':
        return 'New Zealander'
    if code == 'AU':
        return 'Australian'
    return ''


def _fetch_idol_api_payload(member):
    for candidate in _name_candidates(member.stage_name or member.name):
        encoded = urllib.parse.quote(candidate, safe='-')
        url = f'https://kpopping.com/api/idols/{encoded}'
        try:
            raw = _http_get(url)
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict) and payload.get('stageName'):
            payload['profile_source_url'] = url.replace('/api/idols/', '/profiles/idol/')
            return payload
    return {}


def _parse_idol_api_payload(payload):
    biography = _clean_multiline_text(_strip_tags(payload.get('bioRaw') or payload.get('bioHtml') or ''))
    profile_focus = []
    if _clean_text(payload.get('company')):
        profile_focus.append(f"The current solo or individual company file on K-Beats lists {_clean_text(payload.get('company'))}.")
    if _clean_text(payload.get('activeYears')):
        profile_focus.append(f"The idol profile timeline currently reads {_clean_text(payload.get('activeYears'))}.")

    socials = []
    for key, label in (
        ('instagram', 'Instagram'),
        ('twitter', 'X'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
        ('spotify', 'Spotify'),
        ('weibo', 'Weibo'),
        ('website', 'Official site'),
    ):
        url = _clean_text(payload.get(key))
        if url:
            socials.append({'label': label, 'url': url})

    metadata = {
        'status': _clean_text(payload.get('status')).title(),
        'birth_name': _clean_text(payload.get('fullName')),
        'korean_name': _clean_text(payload.get('nativeName')),
        'hometown': _clean_text(payload.get('hometown')),
        'company': _clean_text(payload.get('company')),
        'country': _country_name(payload.get('country')),
        'height_cm': str(payload.get('height') or '').strip(),
        'mbti': _clean_text(payload.get('mbti')),
        'blood_type': _clean_text(payload.get('bloodType')),
        'weight': f"{payload.get('weight')} kg" if payload.get('weight') else '',
        'education': _clean_text(payload.get('education')),
        'biography': biography,
        'profile_focus': " ".join(profile_focus),
        'profile_source_url': _clean_text(payload.get('profile_source_url')),
        'socials': socials,
        'birthdate': _clean_text(payload.get('birthdate')),
        'facts': [
            note for note in [
                f"Stage name: {_clean_text(payload.get('stageName'))}" if payload.get('stageName') else '',
                f"Full name: {_clean_text(payload.get('fullName'))}" if payload.get('fullName') else '',
                f"Status: {_clean_text(payload.get('status')).title()}" if payload.get('status') else '',
                f"Current company: {_clean_text(payload.get('company'))}" if payload.get('company') else '',
                f"Height: {payload.get('height')} cm" if payload.get('height') else '',
                f"Weight: {payload.get('weight')} kg" if payload.get('weight') else '',
                f"Education: {_clean_text(payload.get('education'))}" if payload.get('education') else '',
                f"MBTI: {_clean_text(payload.get('mbti'))}" if payload.get('mbti') else '',
                f"Blood type: {_clean_text(payload.get('bloodType'))}" if payload.get('bloodType') else '',
            ] if note
        ],
    }
    return {key: value for key, value in metadata.items() if value}


def _parse_profile_page(html, member):
    lines = _profile_text_lines(html)
    stage_name = member.display_name
    facts = _extract_facts(lines, stage_name)
    metadata = {
        'status': 'Active',
        'stage_name_display': _extract_label(lines, 'Stage Name'),
        'birth_name': _extract_label(lines, 'Birth Name'),
        'korean_name': _extract_label(lines, 'Korean Name'),
        'birthday_display': _extract_label(lines, 'Birthday'),
        'zodiac_sign': _extract_label(lines, 'Zodiac Sign'),
        'chinese_zodiac': _extract_label(lines, 'Chinese Zodiac Sign'),
        'weight': _extract_label(lines, 'Weight'),
        'unit': _extract_label(lines, 'Unit'),
        'education': _extract_label(lines, 'Education'),
        'hometown': _extract_label(lines, 'Hometown'),
        'profile_source_url': '',
        'facts': facts,
        'socials': _extract_socials(lines),
    }
    return {key: value for key, value in metadata.items() if value}


def _merge_social_links(member, metadata):
    links = []
    seen = set()
    existing = member.official_links or []
    for item in existing:
        if isinstance(item, dict):
            url = str(item.get('url') or item.get('href') or '').strip()
            label = str(item.get('label') or item.get('title') or item.get('name') or '').strip() or 'Official'
        else:
            url = str(item or '').strip()
            label = 'Official'
        if url and url not in seen:
            links.append({'label': label, 'url': url})
            seen.add(url)

    for item in metadata.get('socials', []):
        url = str(item.get('url') or '').strip()
        label = str(item.get('label') or 'Official').strip()
        if url and url not in seen:
            links.append({'label': label, 'url': url})
            seen.add(url)

    return links


def _sync_from_profile_page(member):
    idol_payload = _fetch_idol_api_payload(member)
    if idol_payload:
        return _parse_idol_api_payload(idol_payload)

    for candidate in _name_candidates(member.stage_name or member.name):
        encoded = urllib.parse.quote(candidate, safe='-')
        url = f'https://kpopping.com/profiles/idol/{encoded}'
        try:
            html = _http_get(url)
        except Exception:
            continue
        if 'Profile' not in html and 'Facts' not in html:
            continue
        parsed = _parse_profile_page(html, member)
        if parsed:
            parsed['profile_source_url'] = url
            return parsed
    return {}


class Command(BaseCommand):
    help = 'Sync richer member profile facts from Kpopping profile pages.'

    def add_arguments(self, parser):
        parser.add_argument('--group', help='Only sync one group by slug.')
        parser.add_argument('--member', help='Only sync one member by slug.')
        parser.add_argument('--limit', type=int, default=0, help='Maximum number of members to process.')
        parser.add_argument('--only-missing', action='store_true', help='Only sync members without profile metadata.')
        parser.add_argument('--force', action='store_true', help='Overwrite existing member fields with Kpopping profile data where available.')
        parser.add_argument('--dry-run', action='store_true', help='Show what would change without saving.')

    def handle(self, *args, **options):
        group_slug = str(options.get('group') or '').strip()
        member_slug = str(options.get('member') or '').strip()
        limit = int(options.get('limit') or 0)
        only_missing = bool(options.get('only_missing'))
        force = bool(options.get('force'))
        dry_run = bool(options.get('dry_run'))

        qs = KPopMember.objects.select_related('group').all().order_by('group__name', 'order', 'name')
        if group_slug:
            qs = qs.filter(group__slug=group_slug)
        if member_slug:
            qs = qs.filter(slug=member_slug)
        if only_missing:
            qs = qs.filter(profile_metadata={})

        members = list(qs)
        if limit > 0:
            members = members[:limit]

        if not members:
            self.stdout.write(self.style.WARNING('No members matched the selected filters.'))
            return

        updated = 0
        failed = 0

        for member in members:
            metadata = _sync_from_profile_page(member)
            if not metadata:
                failed += 1
                self.stdout.write(self.style.WARNING(f'FAIL  {member.group.name}/{member.display_name}'))
                continue

            profile_metadata = dict(member.profile_metadata or {})
            profile_metadata.update({key: value for key, value in metadata.items() if key != 'socials'})

            update_fields = ['profile_metadata', 'official_links']
            member.profile_metadata = profile_metadata
            member.official_links = _merge_social_links(member, metadata)

            korean_name = str(metadata.get('korean_name') or '').strip()
            if korean_name and (force or not member.korean_name):
                member.korean_name = korean_name
                update_fields.append('korean_name')

            birth_name = str(metadata.get('birth_name') or '').strip()
            if birth_name and (force or not member.full_name):
                member.full_name = birth_name
                update_fields.append('full_name')

            biography = str(profile_metadata.get('biography') or '').strip()
            if biography and (force or not member.profile_bio):
                member.profile_bio = biography
                update_fields.append('profile_bio')

            if metadata.get('facts') and (force or not member.fan_facts):
                member.fan_facts = "\n".join(metadata.get('facts') or [])
                update_fields.append('fan_facts')

            if _clean_text(metadata.get('country')) and (force or not member.nationality):
                member.nationality = _clean_text(metadata.get('country'))
                update_fields.append('nationality')

            if _clean_text(metadata.get('mbti')) and (force or not member.mbti):
                member.mbti = _clean_text(metadata.get('mbti'))
                update_fields.append('mbti')

            if _clean_text(metadata.get('blood_type')) and (force or not member.blood_type):
                member.blood_type = _clean_text(metadata.get('blood_type'))
                update_fields.append('blood_type')

            if _clean_text(metadata.get('height_cm')) and (force or not member.height_cm):
                try:
                    member.height_cm = int(_clean_text(metadata.get('height_cm')))
                    update_fields.append('height_cm')
                except ValueError:
                    pass

            if force or not member.instagram_url:
                for item in metadata.get('socials', []):
                    if str(item.get('label') or '').lower() == 'instagram':
                        member.instagram_url = str(item.get('url') or '').strip()
                        update_fields.append('instagram_url')
                        break

            birthdate = _iso_to_date(metadata.get('birthdate'))
            if birthdate and (force or not member.date_of_birth):
                member.date_of_birth = birthdate
                update_fields.append('date_of_birth')

            if not dry_run:
                member.save(update_fields=list(dict.fromkeys(update_fields)))

            updated += 1
            self.stdout.write(self.style.SUCCESS(f'OK    {member.group.name}/{member.display_name}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Updated: {updated}'))
        self.stdout.write(self.style.WARNING(f'Failed: {failed}'))
