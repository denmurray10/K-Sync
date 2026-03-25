import json
import hashlib
import logging
import os
import uuid
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from django.db import DatabaseError, models, transaction
from django.utils import timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.conf import settings
from django.urls import reverse
import requests
import urllib.parse
import re
import random
from openai import OpenAI
import bleach
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
import base64
from .models import (
    Ranking, ComebackData, KPopGroup, KPopMember,
    LivePoll, BlogArticle, UserProfile, FavouriteSong,
    RadioTrackPlay,
    GameScore, SongRequest, Contest, ContestEntry,
    FanClubMembership, UserNotification, ClubInvitation, ClubLaunch, UserBadge,
    LimitedTimeEvent, EventBadgeDrop, EventParticipation,
    LiveChatMessage, ChatBlockedTerm,
    RadioTrack, RadioStationState, RadioPlaylist, RadioPlaylistTrack, RadioSchedule,
    RadioScheduleTemplate, RadioScheduleTemplateSlot,
)

def _staff_only_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Authentication required'}, status=403)
    if not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Staff access required'}, status=403)
    return None


def _admin_only_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Authentication required'}, status=403)
    if not request.user.is_superuser:
        return JsonResponse({'ok': False, 'error': 'Admin access required'}, status=403)
    return None


def _radio_track_base_queryset():
    qs = (
        RadioTrack.objects
        .exclude(audio_url='')
        .exclude(audio_url__isnull=True)
    )
    return qs.exclude(audio_url__icontains='versionId=')


def _record_live_track_play(request, track):
    if not request.user.is_authenticated or not track:
        return
    dedupe_cutoff = timezone.now() - timedelta(minutes=20)
    already_recorded = RadioTrackPlay.objects.filter(
        user=request.user,
        track=track,
        listened_at__gte=dedupe_cutoff,
    ).exists()
    if already_recorded:
        return
    RadioTrackPlay.objects.create(user=request.user, track=track)
    _run_progression_unlocks(request.user)


def _award_user_badge(user, name, badge_type='PROGRESSION', is_glowing=True):
    if not user or not user.is_authenticated:
        return False
    _, created = UserBadge.objects.get_or_create(
        user=user,
        name=name,
        defaults={
            'badge_type': badge_type,
            'is_glowing': is_glowing,
        },
    )
    return created


TIER_RANK = {
    'FREE': 0,
    'PLUS': 1,
    'ULTRA': 2,
}


def _user_tier_for_group(user, group):
    if not user or not user.is_authenticated or not group:
        return 'FREE'
    membership = FanClubMembership.objects.filter(user=user, group=group).first()
    if not membership:
        return 'FREE'
    return str(membership.tier or 'FREE').upper()


def _tier_meets_requirement(user_tier, min_tier):
    return TIER_RANK.get(str(user_tier or 'FREE').upper(), 0) >= TIER_RANK.get(str(min_tier or 'FREE').upper(), 0)


def _user_highest_tier(user):
    if not user or not user.is_authenticated:
        return 'FREE'
    highest = 'FREE'
    for membership_tier in FanClubMembership.objects.filter(user=user).values_list('tier', flat=True):
        normalized_tier = str(membership_tier or 'FREE').upper()
        if TIER_RANK.get(normalized_tier, 0) > TIER_RANK.get(highest, 0):
            highest = normalized_tier
    return highest


def _is_poll_early_access_locked(request, poll):
    if not poll or not poll.early_access_starts_at or not poll.early_access_group:
        return False
    now = timezone.now()
    if now >= poll.early_access_starts_at:
        return False
    tier = _user_tier_for_group(request.user, poll.early_access_group)
    return not _tier_meets_requirement(tier, poll.early_access_min_tier)


def _activity_day_set_for_user(user):
    radio_days = set(
        RadioTrackPlay.objects.filter(user=user)
        .values_list('listened_at__date', flat=True)
    )
    game_days = set(
        GameScore.objects.filter(user=user)
        .values_list('played_at__date', flat=True)
    )
    return {d for d in (radio_days | game_days) if d}


def _calculate_activity_streaks(activity_days, today):
    if not activity_days:
        return {'current': 0, 'longest': 0}

    sorted_days = sorted(activity_days)
    longest = 1
    run = 1
    for idx in range(1, len(sorted_days)):
        if sorted_days[idx - 1] + timedelta(days=1) == sorted_days[idx]:
            run += 1
            longest = max(longest, run)
        elif sorted_days[idx - 1] != sorted_days[idx]:
            run = 1

    current = 0
    cursor = today
    while cursor in activity_days:
        current += 1
        cursor = cursor - timedelta(days=1)

    return {'current': current, 'longest': longest}


def _run_progression_unlocks(user):
    if not user or not user.is_authenticated:
        return {'current_streak': 0, 'longest_streak': 0}

    radio_total = RadioTrackPlay.objects.filter(user=user).count()
    game_total = GameScore.objects.filter(user=user).count()
    best_game_streak = int(
        GameScore.objects.filter(user=user).aggregate(best=models.Max('best_streak')).get('best') or 0
    )

    today = timezone.localdate()
    activity_days = _activity_day_set_for_user(user)
    streaks = _calculate_activity_streaks(activity_days, today)

    if radio_total >= 25:
        _award_user_badge(user, 'Radio Starter')
    if radio_total >= 100:
        _award_user_badge(user, 'Radio Loyalist')
    if game_total >= 10:
        _award_user_badge(user, 'Game Challenger')
    if best_game_streak >= 10:
        _award_user_badge(user, 'Streak Spark')
    if streaks['current'] >= 3:
        _award_user_badge(user, 'Daily Pulse - 3 Day')
    if streaks['current'] >= 7:
        _award_user_badge(user, 'Daily Pulse - 7 Day')

    return {
        'radio_total': radio_total,
        'game_total': game_total,
        'best_game_streak': best_game_streak,
        'current_streak': streaks['current'],
        'longest_streak': streaks['longest'],
    }


def _build_stream_audio_url(source_url):
    """Optionally rewrite Backblaze audio URLs through Cloudinary fetch CDN."""
    raw = str(source_url or '').strip()
    if not raw:
        return raw

    if not getattr(settings, 'AUDIO_STREAM_USE_CLOUDINARY_FETCH', False):
        return raw

    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    if not cloud_name:
        return raw

    parsed = urllib.parse.urlparse(raw)
    host = (parsed.netloc or '').lower()
    if not host or 'res.cloudinary.com' in host:
        return raw

    b2_host = urllib.parse.urlparse(getattr(settings, 'B2_DOWNLOAD_URL', '')).netloc.lower()
    is_backblaze = ('backblazeb2.com' in host) or (b2_host and host == b2_host)
    if not is_backblaze:
        return raw

    transform = str(getattr(settings, 'AUDIO_STREAM_CLOUDINARY_TRANSFORM', '') or '').strip()
    encoded = urllib.parse.quote(raw, safe='')
    if transform:
        return f"https://res.cloudinary.com/{cloud_name}/video/fetch/{transform}/{encoded}"
    return f"https://res.cloudinary.com/{cloud_name}/video/fetch/{encoded}"


def _build_stream_image_url(source_url):
    """Optionally rewrite Backblaze image URLs through Cloudinary fetch CDN."""
    raw = str(source_url or '').strip()
    if not raw:
        return raw

    if not getattr(settings, 'IMAGE_STREAM_USE_CLOUDINARY_FETCH', False):
        return raw

    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    if not cloud_name:
        return raw

    parsed = urllib.parse.urlparse(raw)
    host = (parsed.netloc or '').lower()
    if not host or 'res.cloudinary.com' in host:
        return raw

    b2_host = urllib.parse.urlparse(getattr(settings, 'B2_DOWNLOAD_URL', '')).netloc.lower()
    is_backblaze = ('backblazeb2.com' in host) or (b2_host and host == b2_host)
    if not is_backblaze:
        return raw

    transform = str(getattr(settings, 'IMAGE_STREAM_CLOUDINARY_TRANSFORM', '') or '').strip()
    encoded = urllib.parse.quote(raw, safe='')
    if transform:
        return f"https://res.cloudinary.com/{cloud_name}/image/fetch/{transform}/{encoded}"
    return f"https://res.cloudinary.com/{cloud_name}/image/fetch/{encoded}"


DEFAULT_STREAM_IMAGE_URL = "https://res.cloudinary.com/diuanqnce/image/upload/f_auto,q_auto/ksync/about_banner"
KNOWN_BROKEN_IMAGE_FRAGMENTS = (
    "v1710546648/ksync/skz_group_default.jpg",
)


def _is_known_broken_image_url(source_url):
    raw = str(source_url or '').strip()
    if not raw:
        return True
    lowered = raw.lower()
    return any(fragment in lowered for fragment in KNOWN_BROKEN_IMAGE_FRAGMENTS)


def _coalesce_stream_image_url(*candidates, fallback=DEFAULT_STREAM_IMAGE_URL):
    for candidate in candidates:
        raw = str(candidate or '').strip()
        if not raw or _is_known_broken_image_url(raw):
            continue
        cooked = _build_stream_image_url(raw)
        if cooked and not _is_known_broken_image_url(cooked):
            return cooked
    return fallback


def _apply_stream_image_to_field(obj, field_name):
    if not obj or not field_name:
        return
    try:
        current = getattr(obj, field_name, '')
    except Exception:
        return
    try:
        setattr(obj, field_name, _build_stream_image_url(current))
    except Exception:
        pass


def _apply_stream_images_to_article(article):
    if not article:
        return
    _apply_stream_image_to_field(article, 'image')
    _apply_stream_image_to_field(article, 'image_2')
    _apply_stream_image_to_field(article, 'image_3')


def _optimize_home_image_url(source_url, *, width=None, height=None):
    raw = str(source_url or '').strip()
    if not raw:
        return raw

    parsed = urllib.parse.urlparse(raw)
    host = (parsed.netloc or '').lower()

    # Right-size iTunes artwork URLs directly at source.
    if 'is1-ssl.mzstatic.com' in host:
        target = 100 if (width and int(width) <= 120) else 200
        return re.sub(r'/\d+x\d+bb\.', f'/{target}x{target}bb.', raw)

    cloud_name = str(getattr(settings, 'CLOUDINARY_CLOUD_NAME', '') or '').strip()
    if not cloud_name:
        return raw

    transform_parts = ['f_auto', 'q_auto']
    if width:
        transform_parts.append(f'w_{int(width)}')
    if height:
        transform_parts.append(f'h_{int(height)}')
    if width and height:
        transform_parts.append('c_fill')
    transform = ','.join(transform_parts)

    if 'res.cloudinary.com' in host and '/image/upload/' in raw:
        base, tail = raw.split('/image/upload/', 1)
        return f'{base}/image/upload/{transform}/{tail}'

    if 'cdn.kpopping.com' in host or 'backblazeb2.com' in host:
        encoded = urllib.parse.quote(raw, safe='')
        return f'https://res.cloudinary.com/{cloud_name}/image/fetch/{transform}/{encoded}'

    return raw


def _fetch_artwork_from_sources(artist, title):
    artist_text = str(artist or '').strip()
    title_text = str(title or '').strip()
    query = f"{artist_text} {title_text}".strip()
    if not query:
        return ''

    headers = {'User-Agent': 'Mozilla/5.0'}

    # 1) iTunes Search API
    try:
        resp = requests.get(
            'https://itunes.apple.com/search',
            params={'term': query, 'entity': 'song', 'limit': 1},
            headers=headers,
            timeout=3,
        )
        if resp.ok:
            data = resp.json() or {}
            results = data.get('results') or []
            if results:
                art = str(results[0].get('artworkUrl100') or '').strip()
                if art:
                    return (
                        art
                        .replace('100x100bb', '600x600bb')
                        .replace('60x60bb', '600x600bb')
                    )
    except Exception:
        pass

    # 2) Deezer Search API fallback
    try:
        resp = requests.get(
            'https://api.deezer.com/search',
            params={'q': query, 'limit': 1},
            headers=headers,
            timeout=3,
        )
        if resp.ok:
            data = resp.json() or {}
            rows = data.get('data') or []
            if rows:
                album = rows[0].get('album') or {}
                for key in ('cover_xl', 'cover_big', 'cover_medium', 'cover'):
                    art = str(album.get(key) or '').strip()
                    if art:
                        return art
    except Exception:
        pass

    return ''


def _normalize_show_color(raw_value):
    allowed = {'CYAN', 'PINK', 'PURPLE', 'GREEN', 'AMBER'}
    candidate = str(raw_value or '').strip().upper()
    return candidate if candidate in allowed else 'CYAN'


def _sanitize_playlist_name(name):
    cleaned = str(name or '').strip()
    if not cleaned:
        return ''

    cleaned = re.sub(r'\b(AI|DATE|TIME)\b', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b\d{4}-\d{2}-\d{2}(?:\s+\d{1,2}:\d{2})?\b', ' ', cleaned)
    cleaned = re.sub(r'\b\d{1,2}:\d{2}\b', ' ', cleaned)
    cleaned = re.sub(r'[\---|]+', ' ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()

    return cleaned or str(name or '').strip()


def _fallback_playlist_preview(playlist_name, sample_tracks):
    safe_name = _sanitize_playlist_name(playlist_name) or 'this show'
    safe_name_lower = safe_name.lower()
    titles = []
    artists = []
    for track in sample_tracks[:6]:
        title = str(track.get('title') or '').strip()
        artist = str(track.get('artist') or '').strip()
        if title and title not in titles:
            titles.append(title)
        if artist and artist not in artists:
            artists.append(artist)

    lead_artist = artists[0] if artists else 'today\'s featured acts'
    artist_text = ', '.join(artists[:3]) if artists else 'top K-pop favourites and fresh cuts'
    title_a = titles[0] if titles else 'high-impact choruses'
    title_b = titles[1] if len(titles) > 1 else 'smooth transitions'

    if 'album' in safe_name_lower:
        templates = [
            f"{safe_name} spotlights full-album storytelling, moving through deeper cuts from {artist_text} with richer pacing and mood shifts.",
            f"Built for album listeners, {safe_name} leans into sequence and atmosphere, letting standout tracks from {lead_artist} breathe beyond singles.",
            f"From {title_a} to {title_b}, {safe_name} explores long-form K-pop texture with cohesive transitions and deeper catalog moments.",
        ]
    elif 'single' in safe_name_lower:
        templates = [
            f"{safe_name} is all killer hooks and instant payoffs, stacking sharp, chart-ready singles from {artist_text} back-to-back.",
            f"Expect tight runtimes and high-impact choruses on {safe_name}, where {lead_artist} and peers deliver pure headline-single energy.",
            f"{safe_name} keeps things fast and catchy, pivoting from {title_a} into {title_b} with clean, radio-first momentum.",
        ]
    elif 'ep' in safe_name_lower:
        templates = [
            f"{safe_name} highlights mini-album gems, balancing title-track urgency with standout EP b-sides from {artist_text}.",
            f"On {safe_name}, shorter project cuts take centre stage, with {lead_artist} and others driving compact but adventurous transitions.",
            f"{safe_name} bridges {title_a} and {title_b} with a focused EP-driven arc that feels concise, curated and fresh.",
        ]
    else:
        templates = [
            f"Expect a punchy blend from {artist_text}, giving {safe_name} a bright, high-energy flow from start to finish.",
            f"{safe_name} leans into confident hooks and big drops, with {lead_artist} and company shaping a bold primetime mix.",
            f"From {title_a} into {title_b}, this set keeps momentum steady while spotlighting a balanced artist spread.",
            f"This hour on {safe_name} is built for replay value: polished vocals, dynamic production and crowd-ready K-pop moments.",
            f"{safe_name} threads fan favourites with newer sounds, moving cleanly between upbeat peaks and lighter melodic sections.",
        ]

    template_index = uuid.uuid5(uuid.NAMESPACE_DNS, safe_name.lower()).int % len(templates)
    return templates[template_index]


def _generate_playlist_preview(playlist_name, sample_tracks):
    if not sample_tracks:
        return _fallback_playlist_preview(playlist_name, sample_tracks)

    prompt_lines = []
    for track in sample_tracks[:6]:
        title = str(track.get('title') or '').strip()
        artist = str(track.get('artist') or '').strip()
        if title and artist:
            prompt_lines.append(f"- {title} by {artist}")

    prompt = (
        "Write one lively UK-English sentence previewing this radio show playlist. "
        "Length: 14-24 words. Mention the sonic vibe and artist mix. "
        "No emojis, no hashtags, no quotation marks.\n\n"
        f"Show: {_sanitize_playlist_name(playlist_name)}\n"
        "Playlist sample:\n"
        + "\n".join(prompt_lines)
    )

    try:
        text = _chat(prompt, system="You write concise, exciting K-pop radio copy.")
        cleaned = re.sub(r'\s+', ' ', str(text or '').strip()).strip('"\' ')
        if cleaned:
            return cleaned[:180]
    except Exception:
        pass

    return _fallback_playlist_preview(playlist_name, sample_tracks)


def _display_host_name(host):
    raw_host = str(host or '').strip()
    return raw_host


def _is_placeholder_scheduler_host(host):
    raw_host = str(host or '').strip().lower()
    return raw_host in {'', 'ai scheduler', 'auto dj', 'auto-dj', 'autodj'}


def _build_playlist_preview_by_id(playlist_by_id):
    sample_tracks_by_playlist = {playlist_id: [] for playlist_id in playlist_by_id.keys()}
    if sample_tracks_by_playlist:
        for playlist_track in (
            RadioPlaylistTrack.objects
            .select_related('track')
            .filter(playlist_id__in=list(playlist_by_id.keys()))
            .order_by('playlist_id', 'order', 'id')
        ):
            bucket = sample_tracks_by_playlist.get(playlist_track.playlist_id)
            if bucket is None or len(bucket) >= 6:
                continue
            track = playlist_track.track
            if not track:
                continue
            bucket.append({
                'title': track.title,
                'artist': track.artist,
            })

    playlist_preview_by_id = {}
    for playlist_id, playlist in playlist_by_id.items():
        existing_description = str(playlist.description or '').strip()
        has_custom_description = (
            bool(existing_description)
            and not existing_description.lower().startswith('auto-generated by ai scheduler')
        )
        if has_custom_description:
            playlist_preview_by_id[playlist_id] = existing_description
            continue

        playlist_preview_by_id[playlist_id] = _fallback_playlist_preview(
            playlist.name,
            sample_tracks_by_playlist.get(playlist_id, []),
        )
    return playlist_preview_by_id


def _build_assigned_host_maps():
    assigned_host_by_playlist = {}
    assigned_host_by_day = {}

    for row in (
        RadioSchedule.objects
        .exclude(host__isnull=True)
        .exclude(host='')
        .order_by('-id')
        .values('playlist_id', 'host', 'day')
    ):
        playlist_id = row['playlist_id']
        host = row['host']
        day = row['day']
        if playlist_id not in assigned_host_by_playlist and not _is_placeholder_scheduler_host(host):
            assigned_host_by_playlist[playlist_id] = host
        if day not in assigned_host_by_day and not _is_placeholder_scheduler_host(host):
            assigned_host_by_day[day] = host

    for row in (
        RadioScheduleTemplateSlot.objects
        .exclude(host__isnull=True)
        .exclude(host='')
        .order_by('-id')
        .values('playlist_id', 'host')
    ):
        playlist_id = row['playlist_id']
        host = row['host']
        if playlist_id not in assigned_host_by_playlist and not _is_placeholder_scheduler_host(host):
            assigned_host_by_playlist[playlist_id] = host

    global_assigned_host = (
        next(iter(assigned_host_by_playlist.values()), None)
        or next(iter(assigned_host_by_day.values()), None)
    )
    return assigned_host_by_playlist, assigned_host_by_day, global_assigned_host


def _serialize_schedule_slot_common(
    slot,
    playlist_preview_by_id,
    assigned_host_by_playlist,
    assigned_host_by_day,
    global_assigned_host,
):
    resolved_host = slot.host
    if _is_placeholder_scheduler_host(resolved_host):
        resolved_host = (
            assigned_host_by_playlist.get(slot.playlist.id)
            or assigned_host_by_day.get(slot.day)
            or global_assigned_host
            or resolved_host
        )

    return {
        'playlist_id': slot.playlist.id,
        'time_hhmm': slot.start_time.strftime('%H:%M'),
        'until_hhmm': slot.end_time.strftime('%H:%M'),
        'playlist_name': _sanitize_playlist_name(slot.playlist.name),
        'host_name': _display_host_name(resolved_host),
        'playlist_preview': (
            playlist_preview_by_id.get(slot.playlist.id)
            or _fallback_playlist_preview(slot.playlist.name, [])
        ),
        'show_name': slot.description or '',
        'show_color': _normalize_show_color(slot.show_color),
        'voice_over': slot.voice_over or '',
        'genre': slot.genre,
    }


def _station_group_names_from_profile(profile):
    names = set()
    if not profile:
        return []

    if profile.bias and profile.bias.name:
        names.add(profile.bias.name.strip().lower())

    for group in profile.favorite_groups.all():
        if group and group.name:
            names.add(group.name.strip().lower())

    return sorted(names)


def _text_matches_station(text_parts, station_group_names):
    if not station_group_names:
        return False
    merged = ' '.join([str(part or '').lower() for part in text_parts])
    return any(name in merged for name in station_group_names)


def _sort_items_for_station(items, matcher):
    if not items:
        return items
    scored = []
    for idx, item in enumerate(items):
        scored.append((0 if matcher(item) else 1, idx, item))
    scored.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored]


def _maybe_redirect_to_onboarding(request, profile):
    if not request.user.is_authenticated:
        return None
    if not profile or profile.onboarding_completed:
        return None

    exempt_names = {
        'my_station_onboarding',
        'logout',
        'signups_logout',
        'signups_login',
        'admin:index',
    }
    current_name = request.resolver_match.url_name if request.resolver_match else None
    if current_name in exempt_names:
        return None
    return redirect('my_station_onboarding')


@login_required
def my_station_onboarding(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    eras = [
        ('2nd_gen', '2nd Gen Classics (2008-2013)'),
        ('3rd_gen', '3rd Gen Golden Era (2014-2019)'),
        ('4th_gen', '4th Gen Power Wave (2020-2023)'),
        ('5th_gen', '5th Gen Rising Era (2024+)'),
    ]
    timezone_choices = [
        'Europe/London',
        'Europe/Paris',
        'America/New_York',
        'America/Los_Angeles',
        'Asia/Seoul',
        'Asia/Tokyo',
        'Australia/Sydney',
    ]

    if request.method == 'POST':
        selected_group_ids = request.POST.getlist('favorite_groups')
        selected_eras = request.POST.getlist('favorite_eras')
        skip = request.POST.get('skip') == '1'

        if skip:
            profile.onboarding_completed = True
            profile.save(update_fields=['onboarding_completed'])
            return redirect('dashboard')

        groups = list(KPopGroup.objects.filter(id__in=selected_group_ids))
        digest_enabled = request.POST.get('digest_enabled') == '1'
        digest_channel_push = request.POST.get('digest_channel_push') == '1'
        digest_channel_email = request.POST.get('digest_channel_email') == '1'
        digest_timezone = str(request.POST.get('digest_timezone') or 'Europe/London').strip()
        digest_hour_raw = request.POST.get('digest_hour')
        try:
            digest_hour = int(digest_hour_raw)
        except (TypeError, ValueError):
            digest_hour = 8
        digest_hour = max(0, min(23, digest_hour))

        profile.favorite_eras = [
            era for era in selected_eras if era in {key for key, _label in eras}
        ]
        profile.onboarding_completed = True
        profile.digest_enabled = digest_enabled
        profile.digest_channel_push = digest_channel_push
        profile.digest_channel_email = digest_channel_email
        profile.digest_timezone = digest_timezone if digest_timezone in timezone_choices else 'Europe/London'
        profile.digest_hour = digest_hour
        profile.digest_include_comebacks = request.POST.get('digest_include_comebacks') == '1'
        profile.digest_include_birthdays = request.POST.get('digest_include_birthdays') == '1'
        profile.digest_include_chart_jumps = request.POST.get('digest_include_chart_jumps') == '1'

        if profile.digest_enabled and not (profile.digest_channel_push or profile.digest_channel_email):
            profile.digest_channel_push = True

        if not profile.bias and groups:
            profile.bias = groups[0]

        profile.save(update_fields=[
            'favorite_eras',
            'onboarding_completed',
            'bias',
            'digest_enabled',
            'digest_channel_push',
            'digest_channel_email',
            'digest_timezone',
            'digest_hour',
            'digest_include_comebacks',
            'digest_include_birthdays',
            'digest_include_chart_jumps',
        ])
        profile.favorite_groups.set(groups)

        return redirect('dashboard')

    groups = KPopGroup.objects.order_by('name')[:120]
    selected_groups = set(profile.favorite_groups.values_list('id', flat=True))
    selected_eras = set(profile.favorite_eras or [])

    return render(request, 'core/my_station_onboarding.html', {
        'groups': groups,
        'eras': eras,
        'timezone_choices': timezone_choices,
        'selected_groups': selected_groups,
        'selected_eras': selected_eras,
        'profile': profile,
    })

def api_schedule_data(request):
    """Returns the weekly schedule grouped by day for the frontend."""
    schedules = RadioSchedule.objects.select_related('playlist').all()
    playlist_by_id = {s.playlist.id: s.playlist for s in schedules}
    playlist_preview_by_id = _build_playlist_preview_by_id(playlist_by_id)
    assigned_host_by_playlist, assigned_host_by_day, global_assigned_host = _build_assigned_host_maps()
    playlist_duration_map = {
        item['playlist_id']: int(item['total_seconds'] or 0)
        for item in (
            RadioPlaylistTrack.objects
            .values('playlist_id')
            .annotate(total_seconds=models.Sum('track__duration_seconds'))
        )
    }
    
    # Initialize days
    day_map = {
        'MON': [], 'TUE': [], 'WED': [], 'THU': [], 
        'FRI': [], 'SAT': [], 'SUN': []
    }
    
    for s in schedules:
        slot_data = _serialize_schedule_slot_common(
            s,
            playlist_preview_by_id,
            assigned_host_by_playlist,
            assigned_host_by_day,
            global_assigned_host,
        )
        start_seconds = (s.start_time.hour * 3600) + (s.start_time.minute * 60) + s.start_time.second
        end_seconds = (s.end_time.hour * 3600) + (s.end_time.minute * 60) + s.end_time.second
        slot_duration_seconds = max(0, end_seconds - start_seconds)
        playlist_duration_seconds = playlist_duration_map.get(s.playlist.id, 0)

        day_map[s.day].append({
            'id': s.id,
            'day': s.day,
            'time': slot_data['time_hhmm'],
            'duration': f"Until {slot_data['until_hhmm']}",
            'name': slot_data['playlist_name'],
            'show_name': slot_data['show_name'],
            'show_color': slot_data['show_color'],
            'voice_over': slot_data['voice_over'],
            'playlist_id': s.playlist.id,
            'slot_duration_seconds': slot_duration_seconds,
            'playlist_duration_seconds': playlist_duration_seconds,
            'host': slot_data['host_name'],
            'description': (
                slot_data['playlist_preview']
                or s.description
                or s.playlist.description
            ),
            'genre': slot_data['genre'],
            'icon': 'graphic_eq' if slot_data['genre'] == 'LIVE' else 'album',
            'live': False,
            'upcoming': False
        })
    
    # Sort each day by time
    for day in day_map:
        day_map[day].sort(key=lambda x: x['time'])
        
    return JsonResponse(day_map)

@login_required(login_url='/staff/login/')
def playlist_manager(request):
    """Renders the Playlist Manager UI."""
    if not request.user.is_superuser:
        return redirect('signups_login')
    playlists = list(RadioPlaylist.objects.all())
    for playlist in playlists:
        playlist.name = _sanitize_playlist_name(playlist.name)
    return render(request, 'core/playlist_manager.html', {'playlists': playlists})

def api_b2_tracks(request):
    """Lists files from Backblaze B2 bucket."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check
    key_id = settings.B2_KEY_ID
    app_key = settings.B2_APPLICATION_KEY
    bucket_name = settings.B2_BUCKET_NAME
    default_album_art = "https://res.cloudinary.com/diuanqnce/image/upload/v1710546648/ksync/skz_group_default.jpg"
    search_query = (request.GET.get('q') or '').strip().lower()
    group_query = (request.GET.get('group') or request.GET.get('group_name') or '').strip().lower()
    
    if not all([key_id, app_key, bucket_name]):
        return JsonResponse({'ok': False, 'error': 'B2 credentials missing'}, status=500)
    
    try:
        # Auth
        auth_string = 'Basic ' + base64.b64encode(f"{key_id}:{app_key}".encode('ascii')).decode('ascii')
        auth_resp = requests.get('https://api.backblazeb2.com/b2api/v2/b2_authorize_account', headers={'Authorization': auth_string})
        if auth_resp.status_code != 200:
            return JsonResponse({'ok': False, 'error': f'B2 Auth Failed: {auth_resp.text}'}, status=auth_resp.status_code)
            
        auth_data = auth_resp.json()
        token = auth_data['authorizationToken']
        api_url = auth_data['apiUrl']
        account_id = auth_data['accountId']
        
        # List Buckets to get ID
        list_buckets_resp = requests.get(f"{api_url}/b2api/v2/b2_list_buckets?accountId={account_id}", headers={'Authorization': token})
        if list_buckets_resp.status_code != 200:
            return JsonResponse({'ok': False, 'error': f'B2 List Buckets Failed: {list_buckets_resp.text}'}, status=list_buckets_resp.status_code)
            
        buckets = list_buckets_resp.json().get('buckets', [])
        bucket = next((b for b in buckets if b['bucketName'] == bucket_name), None)
        
        if not bucket:
            return JsonResponse({'ok': False, 'error': f'Bucket "{bucket_name}" not found'}, status=404)
            
        # List Files
        files_resp = requests.post(f"{api_url}/b2api/v2/b2_list_file_names", json={'bucketId': bucket['bucketId']}, headers={'Authorization': token})
        if files_resp.status_code != 200:
            return JsonResponse({'ok': False, 'error': f'B2 List Files Failed: {files_resp.text}'}, status=files_resp.status_code)
            
        files = files_resp.json().get('files', [])

        def normalize(text):
            if not text:
                return ''
            return text.strip().lower().replace('_', ' ')

        def prettify_artist(text):
            if not text:
                return ''
            candidate = text.replace('_', ' ').replace('-', ' ').strip()
            candidate = re.sub(r'([a-z])([A-Z])', r'\1 \2', candidate)
            candidate = re.sub(r'\s+', ' ', candidate)
            return candidate

        def artist_from_audio_url(audio_url):
            if not audio_url:
                return ''
            parsed = urllib.parse.urlparse(audio_url)
            path = urllib.parse.unquote(parsed.path or '')
            parts = [p for p in path.split('/') if p]
            if len(parts) >= 2:
                return prettify_artist(parts[-2])
            return ''

        metadata_by_title = {}
        metadata_by_filename = {}
        for radio_track in _radio_track_base_queryset().only('title', 'artist', 'album_art', 'audio_url', 'duration', 'duration_seconds'):
            title_key = normalize(radio_track.title)
            if title_key and title_key not in metadata_by_title:
                metadata_by_title[title_key] = radio_track

            if radio_track.audio_url:
                parsed = urllib.parse.urlparse(radio_track.audio_url)
                path = urllib.parse.unquote(parsed.path or '')
                filename = normalize(path.split('/')[-1])
                if filename and filename not in metadata_by_filename:
                    metadata_by_filename[filename] = radio_track

        tracks = []
        for f in files:
            file_name = f['fileName']
            if not file_name.lower().endswith(('.mp3', '.wav', '.m4a')):
                continue

            path_parts = file_name.split('/')
            parent_folder = path_parts[-2] if len(path_parts) > 1 else ''
            file_leaf = path_parts[-1]
            base_name = file_leaf.rsplit('.', 1)[0]

            parsed_artist = parent_folder or ''
            parsed_title = base_name
            if ' - ' in base_name:
                left, right = base_name.split(' - ', 1)
                if left and right:
                    parsed_artist = left
                    parsed_title = right

            metadata = (
                metadata_by_filename.get(normalize(file_leaf))
                or metadata_by_title.get(normalize(base_name))
                or metadata_by_title.get(normalize(parsed_title))
            )

            metadata_artist = (metadata.artist if metadata else '') or ''
            if metadata_artist.lower() == 'unknown artist':
                metadata_artist = ''

            artist = (
                metadata_artist
                or artist_from_audio_url(metadata.audio_url if metadata else '')
                or prettify_artist(parsed_artist)
                or 'Unknown Artist'
            ).strip()

            album_art = (metadata.album_art if metadata else '') or default_album_art
            duration = (metadata.duration if metadata else '') or '3:00'
            duration_seconds = (metadata.duration_seconds if metadata else 0) or 180
            encoded_name = urllib.parse.quote(file_name, safe='/')
            download_url = f"{auth_data.get('downloadUrl')}/file/{bucket_name}/{encoded_name}"
            stream_url = _build_stream_audio_url(download_url)

            if search_query:
                title_match = search_query in base_name.lower() or search_query in parsed_title.lower()
                artist_match = search_query in artist.lower()
                if not (title_match or artist_match):
                    continue

            if group_query and group_query not in artist.lower():
                continue

            tracks.append({
                'name': file_name,
                'title': parsed_title,
                'artist': artist,
                'album_art': album_art,
                'duration': duration,
                'duration_seconds': duration_seconds,
                'url': stream_url,
                'fileId': f['fileId']
            })
        
        return JsonResponse({'ok': True, 'tracks': tracks})
    except Exception as e:
        logging.exception("B2 API Error")
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def api_playlist_save(request):
    """Saves or updates a playlist and its tracks."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check
    try:
        data = json.loads(request.body)
        playlist_id = data.get('id')
        name = _sanitize_playlist_name(data.get('name'))
        default_voice_id = (data.get('default_voice_id') or '').strip()
        default_voice_name = (data.get('default_voice_name') or '').strip()
        enforce_final_vo_window_raw = data.get('enforce_final_vo_window', True)
        if isinstance(enforce_final_vo_window_raw, str):
            enforce_final_vo_window = enforce_final_vo_window_raw.strip().lower() not in ('0', 'false', 'no', 'off')
        else:
            enforce_final_vo_window = bool(enforce_final_vo_window_raw)
        track_data = data.get('tracks', []) # List of {title, artist, url, album_art, duration}

        def parse_duration_seconds(value):
            if isinstance(value, int):
                return max(0, value)
            if not value:
                return 180
            try:
                parts = str(value).split(':')
                if len(parts) != 2:
                    return 180
                mins = int(parts[0])
                secs = int(parts[1])
                return max(0, mins * 60 + secs)
            except Exception:
                return 180
        
        if not name:
            return JsonResponse({'ok': False, 'error': 'Playlist name is required'}, status=400)
            
        if playlist_id:
            playlist = RadioPlaylist.objects.get(id=playlist_id)
            playlist.name = name
            playlist.default_voice_id = default_voice_id
            playlist.default_voice_name = default_voice_name
            playlist.save()
        else:
            playlist = RadioPlaylist.objects.create(
                name=name,
                default_voice_id=default_voice_id,
                default_voice_name=default_voice_name,
            )
            
        # Clear existing tracks and re-add in order
        RadioPlaylistTrack.objects.filter(playlist=playlist).delete()
        
        for idx, t in enumerate(track_data):
            # Get or create the RadioTrack first
            title = t.get('title', t.get('name', 'Unknown'))
            artist = t.get('artist', 'Unknown Artist')
            audio_url = t.get('url', '')
            album_art = t.get('album_art', '')
            duration = t.get('duration', '3:00')
            duration_seconds = t.get('duration_seconds', parse_duration_seconds(duration))
            voice_over_text = (t.get('voice_over_text') or '').strip()
            voice_over_voice_id = (t.get('voice_over_voice_id') or '').strip()
            voice_over_voice_name = (t.get('voice_over_voice_name') or '').strip()
            voice_over_active = bool(t.get('voice_over_active'))
            duck_volume_percent = t.get('duck_volume_percent', 10)
            voice_over_start_percent = t.get('voice_over_start_percent', 0)
            voice_over_length_percent = t.get('voice_over_length_percent', 22)
            try:
                duck_volume_percent = int(duck_volume_percent)
            except Exception:
                duck_volume_percent = 10
            duck_volume_percent = max(0, min(100, duck_volume_percent))
            try:
                voice_over_start_percent = int(voice_over_start_percent)
            except Exception:
                voice_over_start_percent = 0
            voice_over_start_percent = max(0, min(100, voice_over_start_percent))
            try:
                voice_over_length_percent = int(voice_over_length_percent)
            except Exception:
                voice_over_length_percent = 22
            voice_over_length_percent = max(1, min(100, voice_over_length_percent))
            if voice_over_active:
                max_start = max(0, 100 - voice_over_length_percent)
                min_start = min(max_start, 85) if enforce_final_vo_window else 0
                voice_over_start_percent = max(min_start, min(max_start, voice_over_start_percent))
            else:
                voice_over_start_percent = 0
            
            track, _ = RadioTrack.objects.get_or_create(
                title=title,
                artist=artist,
                defaults={
                    'audio_url': audio_url,
                    'album_art': album_art,
                    'duration': duration,
                    'duration_seconds': duration_seconds,
                }
            )
            # If track exists but URL changed, update it
            changed = False
            if track.audio_url != audio_url:
                track.audio_url = audio_url
                changed = True
            if album_art and track.album_art != album_art:
                track.album_art = album_art
                changed = True
            if duration and track.duration != duration:
                track.duration = duration
                changed = True
            if isinstance(duration_seconds, int) and track.duration_seconds != duration_seconds:
                track.duration_seconds = duration_seconds
                changed = True
            if changed:
                track.save()
                
            RadioPlaylistTrack.objects.create(
                playlist=playlist,
                track=track,
                order=idx,
                voice_over_voice_id=voice_over_voice_id,
                voice_over_voice_name=voice_over_voice_name,
                voice_over_text=voice_over_text,
                voice_over_active=voice_over_active,
                duck_volume_percent=duck_volume_percent,
                voice_over_start_percent=voice_over_start_percent,
                voice_over_length_percent=voice_over_length_percent,
            )
            
        return JsonResponse({'ok': True, 'id': playlist.id})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def api_schedule_save(request):
    """Saves a schedule entry."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check
    try:
        data = json.loads(request.body)
        # We expect a list of schedule items for simplicity, or clear and replace
        # Radio.co style drag-to-calendar
        day = data.get('day')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        playlist_id = data.get('playlist_id')
        schedule_id = data.get('schedule_id')
        show_name = (data.get('show_name') or '').strip()
        show_color = _normalize_show_color(data.get('show_color'))
        voice_over = (data.get('voice_over') or '').strip()
        host = data.get('host', 'Auto DJ')
        genre = data.get('genre', 'MUSIC')
        
        if not all([day, start_time, end_time, playlist_id]):
            return JsonResponse({'ok': False, 'error': 'Missing required fields'}, status=400)

        try:
            start_obj = datetime.strptime(start_time, '%H:%M').time()
            end_obj = datetime.strptime(end_time, '%H:%M').time()
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Invalid time format'}, status=400)

        if start_obj >= end_obj:
            return JsonResponse({'ok': False, 'error': 'End time must be after start time'}, status=400)

        duration_minutes = ((end_obj.hour * 60) + end_obj.minute) - ((start_obj.hour * 60) + start_obj.minute)
        if duration_minutes > 120:
            return JsonResponse({'ok': False, 'error': 'Maximum show length is 2 hours'}, status=400)
            
        playlist = RadioPlaylist.objects.get(id=playlist_id)

        overlap_qs = RadioSchedule.objects.filter(day=day, start_time__lt=end_obj, end_time__gt=start_obj)
        if schedule_id:
            overlap_qs = overlap_qs.exclude(id=schedule_id)

        overlap = overlap_qs.select_related('playlist').first()

        if overlap:
            return JsonResponse({
                'ok': False,
                'error': f'Conflict with {_sanitize_playlist_name(overlap.playlist.name)} ({overlap.start_time.strftime("%H:%M")} - {overlap.end_time.strftime("%H:%M")})'
            }, status=409)

        if schedule_id:
            schedule = RadioSchedule.objects.get(id=schedule_id)
            schedule.day = day
            schedule.start_time = start_time
            schedule.end_time = end_time
            schedule.playlist = playlist
            schedule.description = show_name
            schedule.show_color = show_color
            schedule.voice_over = voice_over
            schedule.host = host
            schedule.genre = genre
            schedule.save()
        else:
            RadioSchedule.objects.create(
                day=day,
                start_time=start_time,
                end_time=end_time,
                playlist=playlist,
                description=show_name,
                show_color=show_color,
                voice_over=voice_over,
                host=host,
                genre=genre
            )
        
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

def api_playlist_data(request, playlist_id):
    """Returns data for a specific playlist."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check
    try:
        playlist = RadioPlaylist.objects.get(id=playlist_id)
        tracks = RadioPlaylistTrack.objects.filter(playlist=playlist).select_related('track')
        
        track_list = []
        for pt in tracks:
            track_list.append({
                'title': pt.track.title,
                'artist': pt.track.artist,
                'url': pt.track.audio_url,
                'album_art': pt.track.album_art,
                'duration': pt.track.duration,
                'duration_seconds': pt.track.duration_seconds,
                'voice_over_voice_id': pt.voice_over_voice_id,
                'voice_over_voice_name': pt.voice_over_voice_name,
                'voice_over_text': pt.voice_over_text,
                'voice_over_active': pt.voice_over_active,
                'duck_volume_percent': pt.duck_volume_percent,
                'voice_over_start_percent': pt.voice_over_start_percent,
                'voice_over_length_percent': pt.voice_over_length_percent,
            })
            
        return JsonResponse({
            'ok': True,
            'playlist': {
                'id': playlist.id,
                'name': _sanitize_playlist_name(playlist.name),
                'default_voice_id': playlist.default_voice_id,
                'default_voice_name': playlist.default_voice_name,
                'tracks': track_list
            }
        })
    except RadioPlaylist.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Playlist not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_playlist_delete(request, playlist_id):
    """Deletes a playlist and related tracks/schedules."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    try:
        playlist = RadioPlaylist.objects.get(id=playlist_id)
    except RadioPlaylist.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Playlist not found'}, status=404)

    try:
        playlist.delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_voiceover_generate(request):
    """Generates a short DJ voice-over script for a track using Inworld Router."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    title = (payload.get('title') or '').strip()
    artist = (payload.get('artist') or '').strip()
    duration = (payload.get('duration') or '').strip()
    playlist_name = (payload.get('playlist_name') or '').strip()
    selected_voice_id = (payload.get('voice_over_voice_id') or '').strip()
    selected_voice_name = (payload.get('voice_over_voice_name') or '').strip()
    style = (payload.get('style') or 'hype').strip().lower()

    if not title:
        return JsonResponse({'ok': False, 'error': 'Track title is required'}, status=400)

    style_hint = {
        'hype': 'high-energy and punchy',
        'smooth': 'smooth and warm',
        'neutral': 'clean and informative',
    }.get(style, 'high-energy and punchy')

    prompt = (
        "Write ONE radio DJ link for this song that sounds broadcast-ready and specific. "
        "Requirements: 2-4 short sentences, max 420 characters, no hashtags, no emojis, no quotation marks. "
        "Use UK English spelling and phrasing throughout. "
        "Vary sentence structure and avoid generic filler phrasing. "
        "Include at least ONE concrete talking point where possible: current single/comeback, tour stop, chart milestone, recent public appearance, fandom reaction, or notable group fact. "
        "If uncertain on a detail, keep it soft and non-factual (e.g., 'fans are buzzing'). Do not invent exact dates/venues. "
        f"Tone: {style_hint}. "
        f"DJ voice persona: {selected_voice_name or selected_voice_id or 'Default DJ'}. "
        f"Track: {title}. "
        f"Artist: {artist or 'Unknown Artist'}. "
        f"Duration: {duration or 'unknown'}. "
        f"Playlist context: {playlist_name or 'General K-pop rotation'}."
    )

    provider = 'deepseek'
    model_name = 'deepseek-chat'
    text = ''

    if settings.INWORLD_API_KEY:
        try:
            text = _inworld_chat(prompt, system="You are a concise K-pop radio host scriptwriter.")
            provider = 'inworld'
            model_name = settings.INWORLD_CHAT_MODEL
        except Exception:
            text = ''

    if not text:
        try:
            text = _chat(prompt, system="You are a concise K-pop radio host scriptwriter.")
            provider = 'deepseek'
            model_name = 'deepseek-chat'
        except Exception as e:
            return JsonResponse({'ok': False, 'error': f'Script generation failed: {str(e)}'}, status=502)

    if not text:
        return JsonResponse({'ok': False, 'error': 'Inworld returned an empty response.'}, status=502)

    line = re.sub(r'\s+', ' ', str(text)).strip()
    line = line.strip('"').strip("'")
    if len(line) > 420:
        line = line[:420].rstrip()

    return JsonResponse({
        'ok': True,
        'voice_over_text': line,
        'provider': provider,
        'model': model_name,
        'voice_over_voice_id': selected_voice_id,
        'voice_over_voice_name': selected_voice_name,
    })


@csrf_exempt
@require_POST
def api_voiceover_synthesize(request):
    """Synthesizes a voice-over script to audio and returns a playlist-ready track."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    if not settings.INWORLD_API_KEY:
        return JsonResponse({'ok': False, 'error': 'Inworld API key is not configured on the server.'}, status=500)

    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    script_text = (payload.get('text') or '').strip()
    voice_id = (payload.get('voice_over_voice_id') or '').strip()
    voice_name = (payload.get('voice_over_voice_name') or '').strip()
    song_title = (payload.get('song_title') or '').strip()

    if not script_text:
        return JsonResponse({'ok': False, 'error': 'Voice-over script is empty.'}, status=400)
    if not voice_id:
        return JsonResponse({'ok': False, 'error': 'Select a DJ voice first.'}, status=400)

    try:
        tts_resp = requests.post(
            f"{settings.INWORLD_API_ROOT.rstrip('/')}/tts/v1/voice",
            headers={
                'Authorization': f"Basic {settings.INWORLD_API_KEY}",
                'Content-Type': 'application/json',
            },
            json={
                'text': script_text,
                'voiceId': voice_id,
                'modelId': settings.INWORLD_TTS_MODEL,
                'audioConfig': {
                    'audioEncoding': 'MP3',
                    'sampleRateHertz': 24000,
                },
                'applyTextNormalization': 'ON',
                'temperature': 1.0,
            },
            timeout=45,
        )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Inworld TTS request failed: {str(e)}'}, status=502)

    if tts_resp.status_code != 200:
        return JsonResponse({'ok': False, 'error': f'Inworld TTS failed: {tts_resp.text[:300]}'}, status=502)

    try:
        data = tts_resp.json()
        audio_b64 = data.get('audioContent') or ''
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Invalid audio payload from Inworld.'}, status=502)

    if not audio_bytes:
        return JsonResponse({'ok': False, 'error': 'Inworld returned empty audio.'}, status=502)

    safe_voice = re.sub(r'[^a-zA-Z0-9_-]+', '-', voice_name or voice_id)[:64].strip('-') or 'dj'
    filename = f"vo_{safe_voice}_{uuid.uuid4().hex[:10]}.mp3"
    relative_dir = os.path.join('radio', 'voiceovers')
    audio_url = ''
    storage_target = 'local'

    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    cloud_key = getattr(settings, 'CLOUDINARY_API_KEY', '')
    cloud_secret = getattr(settings, 'CLOUDINARY_API_SECRET', '')
    can_upload_to_cloudinary = bool(cloud_name and cloud_key and cloud_secret)

    if not can_upload_to_cloudinary:
        return JsonResponse(
            {'ok': False, 'error': 'Cloud voice storage is required. Configure Cloudinary credentials.'},
            status=500,
        )

    try:
        import io
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=cloud_key,
            api_secret=cloud_secret,
            secure=True,
        )

        cloud_result = cloudinary.uploader.upload(
            io.BytesIO(audio_bytes),
            public_id=f"ksync/radio/voiceovers/{os.path.splitext(filename)[0]}",
            resource_type='video',
            format='mp3',
            overwrite=False,
        )
        audio_url = (cloud_result.get('secure_url') or '').strip()
        if not audio_url:
            return JsonResponse({'ok': False, 'error': 'Cloudinary upload returned no URL.'}, status=502)
        storage_target = 'cloudinary'
    except Exception as cloud_err:
        logger.error('Voice-over Cloudinary upload failed: %s', cloud_err)
        return JsonResponse({'ok': False, 'error': 'Cloudinary upload failed for voice-over audio.'}, status=502)

    duration_seconds = 0
    timestamp_info = data.get('timestampInfo') or {}
    word_alignment = timestamp_info.get('wordAlignment') or {}
    char_alignment = timestamp_info.get('characterAlignment') or {}

    try:
        word_ends = word_alignment.get('wordEndTimeSeconds') or []
        if word_ends:
            duration_seconds = int(round(float(word_ends[-1])))
    except Exception:
        duration_seconds = 0

    if duration_seconds <= 0:
        try:
            char_ends = char_alignment.get('characterEndTimeSeconds') or []
            if char_ends:
                duration_seconds = int(round(float(char_ends[-1])))
        except Exception:
            duration_seconds = 0

    if duration_seconds <= 0:
        duration_seconds = int(round(len(script_text.split()) / 2.4))

    duration_seconds = max(1, min(120, duration_seconds))
    duration_label = f"{duration_seconds // 60}:{duration_seconds % 60:02d}"

    track_title_base = song_title or 'Voice Over'
    track_title = f"VO: {track_title_base}"[:300]
    track_artist = (voice_name or voice_id or 'DJ Voice')[:200]

    return JsonResponse({
        'ok': True,
        'track': {
            'title': track_title,
            'artist': track_artist,
            'url': audio_url,
            'storage_target': storage_target,
            'album_art': '',
            'duration': duration_label,
            'duration_seconds': duration_seconds,
            'voice_over_text': '',
            'voice_over_active': False,
            'voice_over_start_percent': 0,
            'voice_over_length_percent': 22,
            'voice_over_voice_id': voice_id,
            'voice_over_voice_name': voice_name,
        },
        'storage_target': storage_target,
        'provider': 'inworld',
        'model': settings.INWORLD_TTS_MODEL,
    })


def api_inworld_voices(request):
    """Returns available Inworld voices for the workspace bound to the API key."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    if not settings.INWORLD_API_KEY:
        return JsonResponse({'ok': False, 'error': 'Inworld API key is not configured on the server.'}, status=500)

    language_filters = request.GET.getlist('languages')
    query_parts = []
    for language in language_filters:
        code = str(language or '').strip()
        if code:
            query_parts.append(('languages', code))

    try:
        response = requests.get(
            f"{settings.INWORLD_API_ROOT.rstrip('/')}/voices/v1/voices",
            headers={
                'Authorization': f"Basic {settings.INWORLD_API_KEY}",
            },
            params=query_parts,
            timeout=20,
        )

        if response.status_code != 200:
            return JsonResponse({'ok': False, 'error': f'Inworld voices request failed: {response.text[:300]}'}, status=502)

        payload = response.json()
        voices = payload.get('voices') or []
        simplified = []
        for voice in voices:
            voice_id = (voice.get('voiceId') or '').strip()
            if not voice_id:
                continue
            simplified.append({
                'voice_id': voice_id,
                'display_name': (voice.get('displayName') or voice_id).strip(),
                'lang_code': (voice.get('langCode') or '').strip(),
                'source': (voice.get('source') or '').strip(),
                'description': (voice.get('description') or '').strip(),
            })

        simplified.sort(key=lambda item: (item.get('display_name') or '').lower())
        return JsonResponse({'ok': True, 'voices': simplified})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_voiceover_ai_scripts(request):
    """Generate DJ-style voice-over scripts for selected tracks in a playlist timeline."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    playlist_name = (payload.get('playlist_name') or 'Playlist').strip()
    raw_tracks = payload.get('tracks') or []
    if not isinstance(raw_tracks, list) or not raw_tracks:
        return JsonResponse({'ok': False, 'error': 'No tracks provided.'}, status=400)

    tracks = []
    for item in raw_tracks[:80]:
        title = (item.get('title') or item.get('name') or '').strip()
        artist = (item.get('artist') or '').strip() or 'Unknown Artist'
        duration = (item.get('duration') or '').strip()
        source_index_raw = item.get('index', None)
        source_index = None
        try:
            if source_index_raw is not None and str(source_index_raw).strip() != '':
                source_index = int(source_index_raw)
        except Exception:
            source_index = None
        if not title:
            continue
        tracks.append({
            'title': title[:300],
            'artist': artist[:200],
            'duration': duration[:20],
            'source_index': source_index,
        })

    if not tracks:
        return JsonResponse({'ok': False, 'error': 'No valid tracks provided.'}, status=400)

    selected_indices = []
    idx = 0
    while idx < len(tracks) and len(selected_indices) < 18:
        selected_indices.append(idx)
        idx += random.choices([1, 2, 3, 4], weights=[0.22, 0.38, 0.27, 0.13], k=1)[0]

    if selected_indices and selected_indices[-1] < len(tracks) - 1 and len(selected_indices) < 18 and random.random() < 0.45:
        selected_indices.append(len(tracks) - 1)

    intro_pool = [
        "Right then, let's keep things moving with this next one.",
        "You're locked in with us, and this one's a proper vibe.",
        "Keeping the momentum rolling, here's what's up next.",
        "Time for another pick from the playlist that hits just right.",
        "Let's dip into something a little special right here.",
        "If you're just joining us, perfect timing for this track.",
        "Straight back into the music with another standout tune.",
        "Let's bring the energy up a notch with this next song.",
        "We're not slowing down-here comes another great one.",
        "Fresh from the queue, this next track deserves your attention.",
        "Settle in, this next moment is one for the fans.",
        "Back to back quality-here's what we've lined up now.",
        "Big mood incoming with this one.",
        "This next song is a lovely switch in flavour.",
        "From one great tune to another, let's go.",
        "Let's stay in that groove and keep it flowing.",
        "Your K-pop soundtrack continues right now.",
        "A quick reset, then straight into this next track.",
        "No filler, just bangers-here's the next one.",
        "Let's queue up something that always lands.",
        "This one's for everyone still singing along at home.",
        "Another brilliant entry coming in hot.",
        "Let's pivot into this next track-trust me on this.",
        "Keeping it smooth and steady with this next tune.",
        "Here's one that always gets a reaction.",
        "Ready for another? Let's get into it.",
        "Let's jump to the next chapter in tonight's playlist.",
        "We've got a strong follow-up coming your way.",
        "Back in the mix now with a fan favourite.",
        "Time to lean into this next song.",
        "This next pick fits the mood perfectly.",
        "Let's carry that feeling forward with this track.",
        "A little something to keep the night moving.",
        "Here comes another one worth turning up for.",
        "I've got a great one lined up right here.",
        "This next cut keeps the set looking sharp.",
        "Let's move into something with real character.",
        "From the same lane but a different flavour, here we go.",
        "You know the drill-another top track incoming.",
        "Plenty more to come, starting with this one.",
        "Let's keep this run going with another gem.",
        "This next selection deserves a proper listen.",
        "Coming in now with a solid follow-on track.",
        "Stay with me-this next one is excellent.",
        "The playlist's in great form, and here's proof.",
        "Next up, a tune that sits beautifully in this set.",
        "No long talk-let's get straight to the music.",
        "We're right in the sweet spot now, here's the next track.",
        "This next song keeps the quality bar high.",
        "Let's roll straight into this one.",
    ]
    random.shuffle(intro_pool)

    skip_phrase_pool = [
        "we jumped over a couple tracks",
        "we fast-tracked through one or two songs",
        "we moved quickly past a few tunes",
        "we took a quick leap in the running order",
        "we skimmed ahead a touch in the playlist",
        "we've hopped forward through a couple of entries",
        "we zipped past a few songs in the queue",
        "we've advanced a little in the set",
        "we rolled forward through a handful of tracks",
        "we took a quick step forward in the playlist",
    ]

    content_angle_pool = [
        "recent release momentum (single/album/comeback)",
        "touring or live-stage buzz",
        "group identity/fandom culture insight",
        "recent media/variety/public appearance",
        "songcraft/performance detail (vocals, rap line, choreography)",
        "chart/streaming momentum in broad terms",
        "what listeners should notice in this next track",
    ]

    assignments = []
    previous_selected = None
    recent_opener_signatures = []

    def opener_signature(text):
        cleaned = re.sub(r'[^a-z0-9\s]', ' ', str(text or '').lower())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        words = cleaned.split(' ')
        return ' '.join(words[:6])

    for selection_idx, track_index in enumerate(selected_indices):
        current = tracks[track_index]
        prev_track = tracks[track_index - 1] if track_index > 0 else None
        next_tracks = tracks[track_index + 1: track_index + 3]
        lead_in_seed = intro_pool[selection_idx % len(intro_pool)]
        content_angle = random.choice(content_angle_pool)

        skipped_tracks = []
        if previous_selected is not None and track_index - previous_selected > 1:
            skipped_tracks = tracks[previous_selected + 1:track_index]

        skipped_clause = 'No skipped songs between your previous scripted break and this one.'
        if skipped_tracks:
            skipped_titles = ', '.join([f"{item['title']} by {item['artist']}" for item in skipped_tracks[:2]])
            skip_hint = random.choice(skip_phrase_pool)
            skipped_clause = (
                f"You are skipping {len(skipped_tracks)} song(s) since your last scripted break. "
                f"Acknowledge this naturally using varied wording (example tone: '{skip_hint}') and optionally mention: {skipped_titles}."
            )

        next_clause = 'No next song context available.'
        if next_tracks:
            next_clause = 'Up next context: ' + ', '.join([f"{item['title']} by {item['artist']}" for item in next_tracks]) + '.'

        prev_clause = 'No previous song context available.'
        if prev_track:
            prev_clause = f"Previous song: {prev_track['title']} by {prev_track['artist']}."

        prompt = (
            "Write one short radio DJ voice-over script for this playlist moment. "
            "Style: energetic, conversational, natural UK radio pacing. "
            "Length: 2-4 short sentences, maximum 520 characters. "
            f"Use this opening style as inspiration (do not copy verbatim): {lead_in_seed} "
            f"Primary content angle for this link: {content_angle}. "
            "Include at least one meaningful insight where possible: latest single/comeback, touring chatter, recent public appearance, fandom reaction, or artist/group fact tied to the moment. "
            "If uncertain on hard facts, use careful wording and avoid exact dates/venues. "
            "If you reference an album, only do so when you are confident; otherwise skip album mention. "
            "Avoid hashtags, emojis, stage directions, and quotation marks. "
            "Avoid repetitive stock phrases; do not default to 'we skipped ahead'. "
            "Vary rhythm and syntax from previous links; do not reuse openings. "
            f"Playlist: {playlist_name}. "
            f"Current song: {current['title']} by {current['artist']}. "
            f"{prev_clause} "
            f"{next_clause} "
            f"{skipped_clause}"
        )

        script = ''
        for _attempt in range(3):
            try:
                candidate = _chat(prompt, system="You are a professional K-pop radio DJ writing short voice links between songs.")
            except Exception:
                candidate = ''

            candidate = re.sub(r'\s+', ' ', str(candidate or '')).strip().strip('"').strip("'")
            sig = opener_signature(candidate)
            if not candidate:
                continue
            if sig and sig in recent_opener_signatures:
                continue
            script = candidate
            break

        if not script:
            fallback = lead_in_seed
            if current.get('title') and current.get('artist'):
                fallback = f"{lead_in_seed} Up now: {current['title']} by {current['artist']}."
            script = re.sub(r'\s+', ' ', fallback).strip().strip('"').strip("'")

        if len(script) > 520:
            script = script[:520].rstrip()
        if not script:
            continue

        opener_sig = opener_signature(script)
        if opener_sig:
            recent_opener_signatures.append(opener_sig)
            if len(recent_opener_signatures) > 5:
                recent_opener_signatures = recent_opener_signatures[-5:]

        assignments.append({
            'index': current.get('source_index') if isinstance(current.get('source_index'), int) else track_index,
            'text': script,
            'mentions_skipped': bool(skipped_tracks),
        })
        previous_selected = track_index

    return JsonResponse({
        'ok': True,
        'assignments': assignments,
        'generated_count': len(assignments),
        'total_tracks': len(tracks),
    })

@csrf_exempt
@require_POST
def api_playlist_ai_generate(request):
    """Generates a playlist draft with DeepSeek from RadioTrack records."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    set_minutes = int(payload.get('set_minutes') or 60)
    set_minutes = max(5, min(360, set_minutes))
    vibe = (payload.get('vibe') or 'balanced').strip().lower()
    era = (payload.get('era') or 'mix').strip().lower()
    familiarity = (payload.get('familiarity') or 'mix').strip().lower()

    track_qs = (
        _radio_track_base_queryset()
        .exclude(duration_seconds__isnull=True)
    )

    now = timezone.now()
    recent_cutoff = now - timedelta(days=730)

    if era == 'new':
        track_qs = track_qs.filter(created_at__gte=recent_cutoff).order_by('-created_at')
    elif era == 'older':
        track_qs = track_qs.filter(created_at__lt=recent_cutoff).order_by('created_at')
    else:
        track_qs = track_qs.order_by('-created_at')

    candidate_tracks = list(track_qs[:450])
    if not candidate_tracks:
        return JsonResponse({'ok': False, 'error': 'No tracks available for AI generation.'}, status=400)

    target_seconds = set_minutes * 60
    # deterministic familiarity proxy prefilter (no explicit popularity field in DB)
    if familiarity == 'popular':
        candidate_tracks = candidate_tracks[:220]
    elif familiarity == 'deep-cuts':
        candidate_tracks = candidate_tracks[len(candidate_tracks)//3:]

    # vibe-based duration preference (deterministic scoring)
    desired_seconds = {
        'energetic': 190,
        'hype': 180,
        'chill': 225,
        'balanced': 205,
    }.get(vibe, 205)

    scored_pool = []
    for track in candidate_tracks:
        seconds = track.duration_seconds or 180
        if seconds < 90 or seconds > 480:
            continue
        score = abs(seconds - desired_seconds)
        scored_pool.append((score, random.random(), track))

    scored_pool.sort(key=lambda x: (x[0], x[1]))
    ordered_pool = [t for _, _, t in scored_pool]

    # deterministic time-fit selection (AI will order flow afterwards)
    selected_tracks = []
    total_seconds = 0
    for track in ordered_pool:
        seconds = track.duration_seconds or 180
        if total_seconds + seconds <= target_seconds + 120:
            selected_tracks.append(track)
            total_seconds += seconds
        if total_seconds >= target_seconds - 60:
            break

    if not selected_tracks:
        selected_tracks = ordered_pool[:max(1, min(15, len(ordered_pool)))]

    by_id = {t.id: t for t in selected_tracks}
    playlist_name = f"AI {set_minutes}min {vibe.title()} Set"

    # Use DeepSeek only to order the preselected subset for better flow
    flow_candidates = [
        f"{t.id}|{t.title}|{t.artist}|{t.duration_seconds or 180}|{t.duration or '3:00'}"
        for t in selected_tracks
    ]
    flow_prompt = (
        "Order these preselected tracks for best radio flow."
        f" Vibe: {vibe}. Era: {era}. Familiarity: {familiarity}."
        " Return STRICT JSON only: {\"name\":\"...\",\"track_ids\":[...]}"
        " using only provided IDs with no duplicates.\n\n"
        "Candidates (id|title|artist|duration_seconds|duration):\n"
        + "\n".join(flow_candidates)
    )

    final_ids = [t.id for t in selected_tracks]
    try:
        ai_text = _chat(flow_prompt, system="You are a precise K-pop radio programmer focused on sequencing.")
        json_match = re.search(r'\{[\s\S]*\}', ai_text)
        if json_match:
            obj = json.loads(json_match.group(0))
            if isinstance(obj.get('name'), str) and obj.get('name').strip():
                playlist_name = obj.get('name').strip()[:120]
            ai_ids = [int(i) for i in (obj.get('track_ids') or []) if str(i).isdigit()]
            deduped = []
            seen = set()
            for track_id in ai_ids:
                if track_id in by_id and track_id not in seen:
                    deduped.append(track_id)
                    seen.add(track_id)
            # append any missing tracks to preserve selection completeness
            for track in selected_tracks:
                if track.id not in seen:
                    deduped.append(track.id)
                    seen.add(track.id)
            if deduped:
                final_ids = deduped
    except Exception:
        pass

    tracks = []
    for track_id in final_ids:
        track = by_id.get(track_id)
        if not track:
            continue
        tracks.append({
            'title': track.title,
            'artist': track.artist,
            'url': track.audio_url,
            'album_art': track.album_art,
            'duration': track.duration or '3:00',
            'duration_seconds': track.duration_seconds or 180,
        })

    return JsonResponse({
        'ok': True,
        'playlist_name': playlist_name,
        'tracks': tracks,
        'target_minutes': set_minutes,
        'total_seconds': sum(t.get('duration_seconds', 0) for t in tracks),
    })


@csrf_exempt
@require_POST
def api_schedule_ai_fill(request):
    """Fills open scheduler gaps with AI-generated playlists without touching existing slots."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    fill_level = (payload.get('fill_level') or 'a_lot').strip().lower()
    vibe = (payload.get('vibe') or 'balanced').strip().lower()
    era = (payload.get('era') or 'mix').strip().lower()
    familiarity = (payload.get('familiarity') or 'mix').strip().lower()
    focus = (payload.get('focus') or 'mix').strip().lower()
    include_artists = (payload.get('include_artists') or '').strip().lower()
    avoid_artists = (payload.get('avoid_artists') or '').strip().lower()

    fill_ratio_map = {
        'a_bit': 0.25,
        'a_lot': 0.60,
        'everything': 1.00,
    }
    fill_ratio = fill_ratio_map.get(fill_level, 0.60)

    day_order = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

    existing = (
        RadioSchedule.objects
        .select_related('playlist')
        .all()
        .order_by('day', 'start_time')
    )

    by_day = {day: [] for day in day_order}
    for slot in existing:
        by_day[slot.day].append(slot)

    assigned_host_by_day = {}
    for day in day_order:
        for slot in by_day[day]:
            if not _is_placeholder_scheduler_host(slot.host):
                assigned_host_by_day[day] = slot.host
                break

    global_fallback_host = (
        RadioSchedule.objects
        .exclude(host__isnull=True)
        .exclude(host='')
        .exclude(host__iexact='AI Scheduler')
        .order_by('-id')
        .values_list('host', flat=True)
        .first()
        or 'Yang'
    )

    def to_minutes(time_obj):
        return (time_obj.hour * 60) + time_obj.minute

    gaps = []
    for day in day_order:
        cursor = 0
        for slot in by_day[day]:
            start_m = to_minutes(slot.start_time)
            end_m = to_minutes(slot.end_time)
            if start_m > cursor:
                gaps.append({'day': day, 'start': cursor, 'end': start_m})
            cursor = max(cursor, end_m)
        if cursor < 1440:
            gaps.append({'day': day, 'start': cursor, 'end': 1440})

    # avoid tiny windows that cannot host meaningful content
    gaps = [gap for gap in gaps if (gap['end'] - gap['start']) >= 30]
    if not gaps:
        return JsonResponse({'ok': False, 'error': 'No open schedule gaps available.'}, status=400)

    total_open_minutes = sum(g['end'] - g['start'] for g in gaps)
    target_fill_minutes = max(30, int(total_open_minutes * fill_ratio))

    allowed_show_lengths = [60, 90, 120]
    length_weights = {60: 0.5, 90: 0.3, 120: 0.2}
    selected_windows = []
    remaining_fill = target_fill_minutes
    for gap in gaps:
        window_start = gap['start']
        while window_start < gap['end'] and remaining_fill > 0:
            available = gap['end'] - window_start
            if available < 60:
                break

            feasible_lengths = [
                length for length in allowed_show_lengths
                if length <= available and length <= remaining_fill
            ]

            if not feasible_lengths:
                break

            chunk = random.choices(
                feasible_lengths,
                weights=[length_weights.get(length, 0.1) for length in feasible_lengths],
                k=1,
            )[0]
            selected_windows.append({'day': gap['day'], 'start': window_start, 'end': window_start + chunk})
            window_start += chunk
            remaining_fill -= chunk
        if remaining_fill <= 0:
            break

    if not selected_windows:
        return JsonResponse({'ok': False, 'error': 'No eligible windows available within 2-hour show limit.'}, status=400)

    track_qs = (
        _radio_track_base_queryset()
        .exclude(duration_seconds__isnull=True)
    )

    now = timezone.now()
    recent_cutoff = now - timedelta(days=730)
    if era == 'new':
        track_qs = track_qs.filter(created_at__gte=recent_cutoff).order_by('-created_at')
    elif era == 'older':
        track_qs = track_qs.filter(created_at__lt=recent_cutoff).order_by('created_at')
    else:
        track_qs = track_qs.order_by('-created_at')

    candidate_tracks = list(track_qs[:700])
    if not candidate_tracks:
        return JsonResponse({'ok': False, 'error': 'No tracks available for AI scheduler.'}, status=400)

    if familiarity == 'popular':
        candidate_tracks = candidate_tracks[:320]
    elif familiarity == 'deep-cuts':
        candidate_tracks = candidate_tracks[len(candidate_tracks)//3:]

    include_terms = [item.strip() for item in include_artists.split(',') if item.strip()]
    avoid_terms = [item.strip() for item in avoid_artists.split(',') if item.strip()]

    def artist_match(track, terms):
        haystack = f"{track.artist or ''} {track.title or ''}".lower()
        return any(term in haystack for term in terms)

    if include_terms:
        included = [track for track in candidate_tracks if artist_match(track, include_terms)]
        if included:
            candidate_tracks = included + [track for track in candidate_tracks if track not in included]

    if avoid_terms:
        candidate_tracks = [track for track in candidate_tracks if not artist_match(track, avoid_terms)]

    desired_seconds = {
        'energetic': 185,
        'hype': 178,
        'chill': 225,
        'balanced': 205,
    }.get(vibe, 205)

    focus_label = {
        'games': 'Game Break',
        'trivia': 'Trivia Block',
        'mix': 'Interactive Mix',
        'variety': 'Variety Set',
    }.get(focus, 'Interactive Mix')

    focus_color = {
        'games': 'PURPLE',
        'trivia': 'AMBER',
        'mix': 'CYAN',
        'variety': 'GREEN',
    }.get(focus, 'CYAN')

    generated_show_names = []
    try:
        name_prompt = (
            "Create short radio show names for K-pop schedule gaps. "
            f"Need exactly {len(selected_windows)} names. "
            f"Focus: {focus}. Vibe: {vibe}. Era: {era}. Familiarity: {familiarity}. "
            "Return STRICT JSON only: {\"names\":[\"...\"]}."
        )
        name_resp = _chat(name_prompt, system="You are a concise K-pop radio naming assistant.")
        match = re.search(r'\{[\s\S]*\}', name_resp)
        if match:
            obj = json.loads(match.group(0))
            raw_names = obj.get('names') or []
            generated_show_names = [str(name).strip()[:80] for name in raw_names if str(name).strip()]
    except Exception:
        generated_show_names = []

    def minutes_to_hhmm(total_minutes):
        safe = max(0, min(1439, int(total_minutes)))
        return f"{safe // 60:02d}:{safe % 60:02d}"

    def select_tracks_for_gap(target_seconds):
        scored_pool = []
        for track in candidate_tracks:
            seconds = track.duration_seconds or 180
            if seconds < 90 or seconds > 480:
                continue
            score = abs(seconds - desired_seconds)
            scored_pool.append((score, random.random(), track))
        scored_pool.sort(key=lambda item: (item[0], item[1]))

        picked = []
        running = 0
        for _, _, track in scored_pool:
            seconds = track.duration_seconds or 180
            if running + seconds <= target_seconds + 120:
                picked.append(track)
                running += seconds
            if running >= target_seconds - 60:
                break

        if not picked:
            picked = [item[2] for item in scored_pool[:10]]
            running = sum((track.duration_seconds or 180) for track in picked)

        return picked, running

    created_count = 0
    created_playlists = []

    with transaction.atomic():
        for idx, gap in enumerate(selected_windows, start=1):
            gap_minutes = gap['end'] - gap['start']
            gap_seconds = gap_minutes * 60
            tracks, total_seconds = select_tracks_for_gap(gap_seconds)
            if not tracks:
                continue

            start_label = minutes_to_hhmm(gap['start'])
            end_label = minutes_to_hhmm(gap['end'])
            show_name = generated_show_names[idx - 1] if idx - 1 < len(generated_show_names) else f"{focus_label} {idx}"
            playlist_name = f"AI {show_name} {gap['day']} {start_label}"

            playlist = RadioPlaylist.objects.create(
                name=playlist_name[:255],
                description=f"Auto-generated by AI Scheduler ({fill_level})."
            )
            created_playlists.append({'id': playlist.id, 'name': playlist.name})

            for order, track in enumerate(tracks):
                RadioPlaylistTrack.objects.create(playlist=playlist, track=track, order=order)

            RadioSchedule.objects.create(
                day=gap['day'],
                start_time=start_label,
                end_time=end_label,
                playlist=playlist,
                description=show_name,
                show_color=focus_color,
                host=assigned_host_by_day.get(gap['day']) or global_fallback_host,
                genre='GAME',
            )
            created_count += 1

    return JsonResponse({
        'ok': True,
        'created_slots': created_count,
        'filled_minutes': sum((gap['end'] - gap['start']) for gap in selected_windows[:created_count]),
        'fill_level': fill_level,
        'created_playlists': created_playlists,
    })

@csrf_exempt
@require_POST
def api_schedule_delete(request, schedule_id):
    """Deletes a schedule entry."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check
    try:
        schedule = RadioSchedule.objects.get(id=schedule_id)
        schedule.delete()
        return JsonResponse({'ok': True})
    except RadioSchedule.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Schedule not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


def api_schedule_templates(request):
    """Returns saved schedule templates."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    templates = RadioScheduleTemplate.objects.prefetch_related('slots__playlist').all()
    payload = []
    for template in templates:
        slots = []
        for slot in template.slots.all():
            slots.append({
                'start_time': slot.start_time.strftime('%H:%M'),
                'end_time': slot.end_time.strftime('%H:%M'),
                'show_name': slot.show_name or '',
                'show_color': _normalize_show_color(slot.show_color),
                'voice_over': slot.voice_over or '',
                'playlist_id': slot.playlist_id,
                'host': _display_host_name(slot.host),
                'genre': slot.genre,
            })
        payload.append({
            'id': template.id,
            'name': template.name,
            'slots': slots,
        })

    return JsonResponse({'ok': True, 'templates': payload})


@csrf_exempt
@require_POST
def api_schedule_template_save(request):
    """Creates or updates a schedule template by name."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check

    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        slots_data = data.get('slots') or []

        if not name:
            return JsonResponse({'ok': False, 'error': 'Template name is required'}, status=400)
        if not isinstance(slots_data, list):
            return JsonResponse({'ok': False, 'error': 'Slots must be a list'}, status=400)

        playlist_ids = [slot.get('playlist_id') for slot in slots_data if slot.get('playlist_id')]
        playlist_map = RadioPlaylist.objects.in_bulk(playlist_ids)

        template, _ = RadioScheduleTemplate.objects.get_or_create(name=name)
        template.slots.all().delete()

        for idx, slot_data in enumerate(slots_data):
            playlist_id = slot_data.get('playlist_id')
            playlist = playlist_map.get(playlist_id)
            if not playlist:
                return JsonResponse({'ok': False, 'error': f'Playlist not found: {playlist_id}'}, status=400)

            try:
                start_obj = datetime.strptime(slot_data.get('start_time', ''), '%H:%M').time()
                end_obj = datetime.strptime(slot_data.get('end_time', ''), '%H:%M').time()
            except Exception:
                return JsonResponse({'ok': False, 'error': 'Invalid slot time format'}, status=400)

            if start_obj >= end_obj:
                return JsonResponse({'ok': False, 'error': 'Template slot end must be after start'}, status=400)

            RadioScheduleTemplateSlot.objects.create(
                template=template,
                start_time=start_obj,
                end_time=end_obj,
                show_name=(slot_data.get('show_name') or '').strip(),
                show_color=_normalize_show_color(slot_data.get('show_color')),
                voice_over=(slot_data.get('voice_over') or '').strip(),
                playlist=playlist,
                host=slot_data.get('host') or 'Auto DJ',
                genre=slot_data.get('genre') or 'MUSIC',
                order=idx,
            )

        return JsonResponse({'ok': True, 'id': template.id})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def api_schedule_template_delete(request, template_id):
    """Deletes a saved schedule template."""
    staff_check = _admin_only_json(request)
    if staff_check:
        return staff_check
    try:
        template = RadioScheduleTemplate.objects.get(id=template_id)
        template.delete()
        return JsonResponse({'ok': True})
    except RadioScheduleTemplate.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Template not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

logger = logging.getLogger(__name__)

# â”€â”€ DeepSeek client â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _ds_client():
    return OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url='https://api.deepseek.com',
    )

def _chat(prompt, system="You are an expert K-Pop radio assistant."):
    client = _ds_client()
    resp = client.chat.completions.create(
        model='deepseek-chat',
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user',   'content': prompt},
        ],
        max_tokens=8000,
        temperature=0.8,
    )
    return resp.choices[0].message.content.strip()


def _chat_reasoner(prompt, system="You are an expert K-Pop journalist."):
    """Use DeepSeek Reasoner (R1) for higher-quality long-form text generation."""
    client = _ds_client()
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    resp = client.chat.completions.create(
        model='deepseek-reasoner',
        messages=messages,
        max_tokens=8000,
    )
    return resp.choices[0].message.content.strip()


def _inworld_chat(prompt, system="You are an expert K-Pop radio assistant."):
    """Calls Inworld Router chat completions endpoint."""
    body = {
        'model': settings.INWORLD_CHAT_MODEL,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.8,
        'max_tokens': 220,
    }

    response = requests.post(
        f"{settings.INWORLD_BASE_URL.rstrip('/')}/chat/completions",
        headers={
            'Authorization': f"Basic {settings.INWORLD_API_KEY}",
            'Content-Type': 'application/json',
        },
        json=body,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:500]}")

    payload = response.json()
    choices = payload.get('choices') or []
    if not choices:
        return ''
    message = choices[0].get('message') or {}
    return (message.get('content') or '').strip()

# â”€â”€ Page views â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _render_frameable_page(request, template_name, context):
    response = render(request, template_name, context)
    response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


def _build_homepage_context(request):
    profile = None
    station_group_names = []
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        onboarding_redirect = _maybe_redirect_to_onboarding(request, profile)
        if onboarding_redirect:
            return onboarding_redirect
        station_group_names = _station_group_names_from_profile(profile)

    now = timezone.now()
    now_uk = timezone.localtime(now, ZoneInfo('Europe/London'))
    data_current = ComebackData.objects.filter(year=now.year, month=now.month).first()
    data_next = ComebackData.objects.filter(year=now.year if now.month < 12 else now.year + 1, 
                                            month=now.month + 1 if now.month < 12 else 1).first()
    
    def _release_image_url(release):
        if not isinstance(release, dict):
            return ''
        for key in ('image', 'image_url', 'cover', 'cover_url', 'thumbnail', 'artwork_url'):
            value = str(release.get(key) or '').strip()
            if value:
                return value
        return ''

    all_releases = []
    if data_current:
        for date_key, details in data_current.data.items():
            if 'releases' in details:
                # date_key is '2026-03-27' based on the error
                resolved_date_str = date_key
                for r in details['releases']:
                    release_item = dict(r)
                    release_item['image'] = _release_image_url(release_item)
                    release_item['date_str'] = resolved_date_str
                    release_item['iso_date'] = f"{resolved_date_str}T09:00:00Z"
                    all_releases.append(release_item)
    
    if data_next:
        for date_key, details in data_next.data.items():
             if 'releases' in details:
                resolved_date_str = date_key
                for r in details['releases']:
                    release_item = dict(r)
                    release_item['image'] = _release_image_url(release_item)
                    release_item['date_str'] = resolved_date_str
                    release_item['iso_date'] = f"{resolved_date_str}T09:00:00Z"
                    all_releases.append(release_item)

    all_releases.sort(key=lambda x: x['date_str'])
    today_str = now.strftime('%Y-%m-%d')
    upcoming_all = [r for r in all_releases if r['date_str'] >= today_str][:20]
    if station_group_names:
        upcoming_all = _sort_items_for_station(
            upcoming_all,
            lambda release: _text_matches_station(
                [release.get('artist'), release.get('title')],
                station_group_names,
            ),
        )

    # Fill comeback artwork from external providers (iTunes -> Deezer), then
    # fall back to the source image from the feed when no match is found.
    artwork_cache = {}
    for release in upcoming_all:
        source_image = str(release.get('image') or '').strip()
        cache_key = (
            str(release.get('artist') or '').strip().lower(),
            str(release.get('title') or '').strip().lower(),
        )
        if cache_key not in artwork_cache:
            artwork_cache[cache_key] = _fetch_artwork_from_sources(
                release.get('artist'),
                release.get('title'),
            )
        release['image'] = artwork_cache.get(cache_key, '') or source_image

    hero_day_events = []
    if upcoming_all:
        first_day = str(upcoming_all[0].get('date_str') or '').strip()
        if first_day:
            hero_day_events = [
                release for release in upcoming_all
                if str(release.get('date_str') or '').strip() == first_day
            ][:12]

    upcoming = [dict(release) for release in upcoming_all[:4]]
    for release in upcoming:
        release['image'] = _optimize_home_image_url(release.get('image'), width=192, height=192)
    upcoming_ticker = upcoming_all[4:20]
    
    # Ensure ticker isn't empty if we have releases but not enough for a separate ticker
    if not upcoming_ticker and upcoming:
        upcoming_ticker = upcoming

    # Trending Sidebar: Use daily ranking data (now synced from iChart)
    daily_rank = Ranking.objects.filter(timeframe='daily').first()
    trending_last_updated = daily_rank.created_at if daily_rank else None
    trending_all = []
    if daily_rank and daily_rank.ranking_data:
        raw_trending = daily_rank.ranking_data[:20]
        
        for idx, item in enumerate(raw_trending):
            img_url = item.get('artwork_url')
            if not img_url:
                img_url = f"https://api.dicebear.com/7.x/initials/svg?seed={item.get('artist')}&backgroundColor=f425c0"
            
            trend_raw = item.get('trend')
            if trend_raw and trend_raw != '-':
                # Handle actual movement from the scraped data
                if '+' in trend_raw or 'â–²' in trend_raw:
                    trend_icon = 'â–²'
                    trend_class = 'text-primary'
                    trend_value = ''.join(filter(str.isdigit, trend_raw))
                elif '-' in trend_raw or 'â–¼' in trend_raw:
                    trend_icon = 'â–¼'
                    trend_class = 'text-slate-500'
                    trend_value = ''.join(filter(str.isdigit, trend_raw))
                else:
                    trend_icon = '-'
                    trend_class = 'text-slate-500'
                    trend_value = ''
            else:
                # Flatline for no movement
                trend_icon = '-'
                trend_class = 'text-slate-500'
                trend_value = ''
            
            trending_all.append({
                'rank': idx + 1,
                'artist': item.get('artist'),
                'title': item.get('track'),
                'image': _optimize_home_image_url(img_url, width=100, height=100),
                'trend_icon': trend_icon,
                'trend_class': trend_class,
                'trend_value': trend_value,
            })
            
    if station_group_names:
        trending_all = _sort_items_for_station(
            trending_all,
            lambda track: _text_matches_station(
                [track.get('artist'), track.get('title')],
                station_group_names,
            ),
        )

    trending = trending_all[:10]
    if trending_all[10:20]:
        trending_ticker = trending_all[10:20]
    else:
        # If we only have 10 or fewer items, duplicate them but with ranks 11-20
        trending_ticker = [{**item, 'rank': item['rank'] + 10} for item in trending_all[:10]]
    
    # Fallback if DB is empty for the first 10
    if not trending and all_releases:
        trending = []
        for idx, r in enumerate(all_releases[:10]):
            trending.append({
                'rank': idx + 1,
                'artist': r.get('artist'),
                'title': r.get('title'),
                'image': r.get('image'),
                'trend_icon': '-',
                'trend_class': 'text-slate-500',
                'trend_value': '',
            })
        
        trending_ticker = []
        ticker_source = all_releases[10:20] if len(all_releases) >= 20 else all_releases[:10]
        for idx, r in enumerate(ticker_source):
            trending_ticker.append({
                'rank': idx + 11,
                'artist': r.get('artist'),
                'title': r.get('title'),
                'image': r.get('image'),
                'trend_icon': '-',
                'trend_class': 'text-slate-500',
                'trend_value': '',
            })

    # Latest news/blog articles
    news_articles = list(BlogArticle.objects.order_by('-created_at')[:3])
    for article in news_articles:
        article.image = _optimize_home_image_url(getattr(article, 'image', ''), width=900)
    featured_article = news_articles[0] if news_articles else None

    # Get the active LivePoll
    active_poll = LivePoll.objects.filter(is_active=True).first()

    # Homepage programming rail: next 4 schedule slots starting from current (if any)
    day_keys = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    current_day_index = now_uk.weekday()  # Monday=0 (UK local day)
    current_minutes = (now_uk.hour * 60) + now_uk.minute

    schedule_items = []
    all_schedules = list(RadioSchedule.objects.select_related('playlist').all())
    playlist_by_id = {s.playlist.id: s.playlist for s in all_schedules if s.playlist_id}
    playlist_preview_by_id = _build_playlist_preview_by_id(playlist_by_id)
    assigned_host_by_playlist, assigned_host_by_day, global_assigned_host = _build_assigned_host_maps()

    for slot in all_schedules:
        day_key = str(slot.day or '').upper()
        if day_key not in day_keys:
            continue
        day_index = day_keys.index(day_key)
        day_delta = (day_index - current_day_index) % 7
        start_minutes = (slot.start_time.hour * 60) + slot.start_time.minute
        end_minutes = (slot.end_time.hour * 60) + slot.end_time.minute
        is_current = day_delta == 0 and start_minutes <= current_minutes < end_minutes
        schedule_items.append({
            'slot': slot,
            'day_delta': day_delta,
            'start_minutes': start_minutes,
            'is_current': is_current,
        })

    schedule_items.sort(key=lambda item: (item['day_delta'], item['start_minutes']))

    start_index = 0
    current_index = next((idx for idx, item in enumerate(schedule_items) if item['is_current']), None)
    if current_index is not None:
        start_index = current_index
    else:
        upcoming_today_index = next(
            (
                idx for idx, item in enumerate(schedule_items)
                if item['day_delta'] == 0 and item['start_minutes'] >= current_minutes
            ),
            None,
        )
        if upcoming_today_index is not None:
            start_index = upcoming_today_index

    homepage_programming = []
    if schedule_items:
        take_count = min(4, len(schedule_items))
        for offset in range(take_count):
            selected = schedule_items[(start_index + offset) % len(schedule_items)]
            slot = selected['slot']
            slot_data = _serialize_schedule_slot_common(
                slot,
                playlist_preview_by_id,
                assigned_host_by_playlist,
                assigned_host_by_day,
                global_assigned_host,
            )
            title = (slot.description or '').strip() or slot.playlist.name
            if selected['is_current'] and offset == 0:
                status = 'On Air'
            elif offset == 0:
                status = 'Up Next'
            else:
                status = ''
            host_name = slot_data['host_name'] or 'Yang'
            playlist_preview = slot_data['playlist_preview']
            description = f"Hosted by {host_name} - {playlist_preview}"
            homepage_programming.append({
                'status': status,
                'time_label': slot_data['time_hhmm'],
                'duration_label': f"Until {slot_data['until_hhmm']}",
                'title': title,
                'description': description,
            })

    # Live player snapshot for homepage now-playing bar
    home_live_track = None
    try:
        state, _ = RadioStationState.objects.get_or_create(id=1)
        schedule_context = _compute_schedule_live_context(timezone.localtime())
        if schedule_context:
            state = _sync_state_with_schedule_context(state, schedule_context)
            candidate_track = schedule_context.get('current_track')
        else:
            state = _auto_rotate_station(state)
            candidate_track = state.current_track if state else None

        if candidate_track and not _is_generated_voice_track(candidate_track):
            home_live_track = {
                'title': candidate_track.title,
                'artist': candidate_track.artist,
            }
    except Exception:
        home_live_track = None
    
    hero_primary_event = hero_day_events[0] if hero_day_events else (upcoming[0] if upcoming else None)
    hero_support_events = hero_day_events[1:4] if len(hero_day_events) > 1 else upcoming[1:4]

    return {
        'upcoming_comebacks': upcoming,
        'hero_day_events': hero_day_events,
        'hero_primary_event': hero_primary_event,
        'hero_support_events': hero_support_events,
        'upcoming_ticker': upcoming_ticker,
        'trending_tracks': trending,
        'trending_ticker_tracks': trending_ticker,
        'trending_last_updated': trending_last_updated,
        'news_articles': news_articles,
        'featured_article': featured_article,
        'current_month': now.strftime('%B %Y'),
        'active_poll': active_poll,
        'home_live_track': home_live_track,
        'homepage_programming': homepage_programming,
        'my_station_profile': profile,
        'my_station_groups': station_group_names,
    }


def home(request):
    context = _build_homepage_context(request)
    if not isinstance(context, dict):
        return context
    return _render_frameable_page(request, 'core/index.html', context)


def home_redesign_lab(request):
    context = _build_homepage_context(request)
    if not isinstance(context, dict):
        return context

    context['redesign_summary'] = [
        {
            'title': 'Signal-panel hero',
            'summary': 'The stacked comeback cards are replaced with a broadcast control panel that surfaces live status, the next event, and stronger top-fold actions.',
        },
        {
            'title': 'Sharper section hierarchy',
            'summary': 'Programming, trending, upcoming releases, and news now each have one dominant focal point instead of multiple equal-weight blocks.',
        },
        {
            'title': 'Cleaner comparison build',
            'summary': 'The redesign drops the client-side artwork fetch pattern and avoids the null-target particle logic that currently adds console noise.',
        },
    ]
    return _render_frameable_page(request, 'core/home_redesign_lab.html', context)


def upcoming_comebacks_design_lab(request):
    now = timezone.now()
    data_current = ComebackData.objects.filter(year=now.year, month=now.month).first()
    data_next = ComebackData.objects.filter(
        year=now.year if now.month < 12 else now.year + 1,
        month=now.month + 1 if now.month < 12 else 1,
    ).first()

    def _release_image_url(release):
        if not isinstance(release, dict):
            return ''
        for key in ('image', 'image_url', 'cover', 'cover_url', 'thumbnail', 'artwork_url'):
            value = str(release.get(key) or '').strip()
            if value:
                return value
        return ''

    all_releases = []
    for data_obj in (data_current, data_next):
        if not data_obj:
            continue
        for date_key, details in (data_obj.data or {}).items():
            for r in (details or {}).get('releases', []) or []:
                release_item = dict(r)
                release_item['image'] = _release_image_url(release_item)
                release_item['date_str'] = str(date_key).strip()
                release_item['iso_date'] = f"{date_key}T09:00:00Z"
                all_releases.append(release_item)

    all_releases.sort(key=lambda x: x.get('date_str', ''))
    today_str = now.strftime('%Y-%m-%d')
    upcoming = [r for r in all_releases if str(r.get('date_str') or '') >= today_str][:9]
    artwork_cache = {}
    for release in upcoming:
        source_image = str(release.get('image') or '').strip()
        cache_key = (
            str(release.get('artist') or '').strip().lower(),
            str(release.get('title') or '').strip().lower(),
        )
        if cache_key not in artwork_cache:
            artwork_cache[cache_key] = _fetch_artwork_from_sources(
                release.get('artist'),
                release.get('title'),
            )
        image_url = artwork_cache.get(cache_key, '') or source_image
        release['image'] = _optimize_home_image_url(image_url, width=320, height=320)

    return render(request, 'core/upcoming_comebacks_design_lab.html', {
        'upcoming_comebacks': upcoming,
        'current_month': now.strftime('%B %Y'),
    })


def _build_header_mega_menu_context(request):
    now_local = timezone.localtime()
    today_str = now_local.strftime('%Y-%m-%d')

    def _safe_id(*parts):
        text = '-'.join([str(part or '').strip().lower() for part in parts if str(part or '').strip()])
        text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
        return text or f'item-{uuid.uuid4().hex[:8]}'

    def _release_image_url(release):
        if not isinstance(release, dict):
            return ''
        for key in ('image', 'image_url', 'cover', 'cover_url', 'thumbnail', 'artwork_url'):
            value = str(release.get(key) or '').strip()
            if value:
                return value
        return ''

    def _format_listener_count(value):
        try:
            return f"{int(value):,} listening"
        except Exception:
            return "Live now"

    data_current = ComebackData.objects.filter(year=now_local.year, month=now_local.month).first()
    data_next = ComebackData.objects.filter(
        year=now_local.year if now_local.month < 12 else now_local.year + 1,
        month=now_local.month + 1 if now_local.month < 12 else 1,
    ).first()

    all_releases = []
    for data_obj in (data_current, data_next):
        if not data_obj:
            continue
        for date_key, details in (data_obj.data or {}).items():
            for release in (details or {}).get('releases', []) or []:
                item = dict(release)
                item['date_str'] = str(date_key).strip()
                item['image'] = _release_image_url(item)
                all_releases.append(item)

    all_releases.sort(key=lambda item: item.get('date_str', ''))
    upcoming_releases = [item for item in all_releases if str(item.get('date_str') or '') >= today_str]
    artwork_cache = {}
    for release in upcoming_releases[:12]:
        source_image = str(release.get('image') or '').strip()
        cache_key = (
            str(release.get('artist') or '').strip().lower(),
            str(release.get('title') or '').strip().lower(),
        )
        if cache_key not in artwork_cache:
            artwork_cache[cache_key] = _fetch_artwork_from_sources(
                release.get('artist'),
                release.get('title'),
            )
        image_url = artwork_cache.get(cache_key, '') or source_image
        release['image'] = _optimize_home_image_url(image_url, width=720, height=720)

    live_track = None
    schedule_context = None
    listeners_label = "Live now"
    live_programming = []
    stream_cards = []
    try:
        state, _ = RadioStationState.objects.get_or_create(id=1)
        schedule_context = _compute_schedule_live_context(now_local)
        if schedule_context:
            state = _sync_state_with_schedule_context(state, schedule_context)
            current_track = schedule_context.get('current_track')
            live_track = current_track
        else:
            state = _auto_rotate_station(state)
            live_track = state.current_track if state else None

        listeners_label = _format_listener_count(getattr(state, 'listeners_count', 0))

        all_schedules = list(RadioSchedule.objects.select_related('playlist').all())
        playlist_by_id = {slot.playlist.id: slot.playlist for slot in all_schedules if slot.playlist_id}
        playlist_preview_by_id = _build_playlist_preview_by_id(playlist_by_id)
        assigned_host_by_playlist, assigned_host_by_day, global_assigned_host = _build_assigned_host_maps()
        day_keys = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        current_day_index = now_local.weekday()
        current_minutes = (now_local.hour * 60) + now_local.minute
        schedule_items = []

        for slot in all_schedules:
            day_key = str(slot.day or '').upper()
            if day_key not in day_keys:
                continue
            day_index = day_keys.index(day_key)
            day_delta = (day_index - current_day_index) % 7
            start_minutes = (slot.start_time.hour * 60) + slot.start_time.minute
            end_minutes = (slot.end_time.hour * 60) + slot.end_time.minute
            is_current = day_delta == 0 and start_minutes <= current_minutes < end_minutes
            schedule_items.append({
                'slot': slot,
                'day_delta': day_delta,
                'start_minutes': start_minutes,
                'is_current': is_current,
            })

        schedule_items.sort(key=lambda item: (item['day_delta'], item['start_minutes']))
        start_index = 0
        current_index = next((idx for idx, item in enumerate(schedule_items) if item['is_current']), None)
        if current_index is not None:
            start_index = current_index
        else:
            upcoming_today_index = next(
                (
                    idx for idx, item in enumerate(schedule_items)
                    if item['day_delta'] == 0 and item['start_minutes'] >= current_minutes
                ),
                None,
            )
            if upcoming_today_index is not None:
                start_index = upcoming_today_index

        if schedule_items:
            take_count = min(3, len(schedule_items))
            selected_schedule_items = [schedule_items[(start_index + offset) % len(schedule_items)] for offset in range(take_count)]

            for offset, selected in enumerate(selected_schedule_items):
                slot = selected['slot']
                slot_data = _serialize_schedule_slot_common(
                    slot,
                    playlist_preview_by_id,
                    assigned_host_by_playlist,
                    assigned_host_by_day,
                    global_assigned_host,
                )
                host_name = slot_data['host_name'] or 'K-Beats'
                show_name = str(slot.description or '').strip() or slot_data['playlist_name']
                title = show_name
                status = 'On Air' if selected['is_current'] and offset == 0 else ('Up Next' if offset == 0 else '')
                short_preview = _shorten_text(slot_data['playlist_preview'], 110)
                live_programming.append({
                    'status': status,
                    'time_label': slot_data['time_hhmm'],
                    'title': title,
                    'description': f"Hosted by {host_name} - {short_preview}",
                })

        base_track_title = getattr(live_track, 'title', '') or 'K-Beats Live'
        base_track_artist = getattr(live_track, 'artist', '') or 'K-Beats'
        base_track_image = _optimize_home_image_url(getattr(live_track, 'album_art', ''), width=1200, height=1200)
        for preset in _stream_presets():
            required_tier = str(preset.get('required_tier') or 'FREE').upper()
            stream_cards.append({
                'id': preset['slug'],
                'preset': preset['preset'],
                'name': preset['name'],
                'short': _shorten_text(preset['tagline'], 84),
                'tagline': preset['tagline'],
                'description': _shorten_text(preset['description'], 180),
                'genres': list(preset.get('genres') or []),
                'accentRgb': preset['accent'],
                'secondaryRgb': preset['secondary'],
                'image': base_track_image,
                'href': reverse('stream_player', args=[preset['slug']]),
                'track': base_track_title,
                'artist': base_track_artist,
                'audience': listeners_label,
                'tier': 'free' if required_tier == 'FREE' else 'premium',
                'mood': preset['mood'],
                'energy': 92 if required_tier == 'ULTRA' else (76 if required_tier == 'PLUS' else 64),
                'energyLabel': preset['description'],
                'peak': preset['preset'],
                'peakNote': preset['note'],
                'peakShort': required_tier,
                'bestFor': preset['best_for'],
                'note': preset['note'],
                'rowTone': 'Premium' if required_tier != 'FREE' else 'Open',
                'perks': list(preset.get('perks') or []),
                'panelLine': _shorten_text(preset['tagline'], 120),
            })
    except Exception:
        live_track = None
        stream_cards = []
        live_programming = []

    rankings = []
    ranking_obj = Ranking.objects.filter(timeframe='daily').first()
    raw_rankings = list((ranking_obj.ranking_data or []) if ranking_obj else [])
    for idx, item in enumerate(raw_rankings[:3]):
        trend_text = str(item.get('trend') or '').strip() or 'Stable'
        metric_support = _shorten_text(item.get('primary_metric_support') or '', 120)
        img_url = _optimize_home_image_url(item.get('artwork_url') or '', width=1200, height=1200)
        rankings.append({
            'id': _safe_id(item.get('artist'), item.get('track'), idx + 1),
            'kicker': f"Rank #{idx + 1}",
            'rank': f"#{idx + 1}",
            'rankLine': 'Latest daily sync',
            'status': trend_text,
            'title': f"{item.get('track') or 'Untitled'} - {item.get('artist') or 'Unknown artist'}",
            'tagline': metric_support or 'Latest chart position from the current K-Beats ranking sync.',
            'description': metric_support or 'Current daily chart placement based on the latest ranking import.',
            'chips': [f"Artist - {item.get('artist') or 'Unknown'}", f"Trend - {trend_text}", f"Type - Daily"],
            'image': img_url,
            'momentumValue': trend_text,
            'momentumTitle': 'Trend',
            'momentumCopy': metric_support or 'No extra chart note available in the current ranking payload.',
            'fastRead': [f"Rank {idx + 1}", item.get('artist') or 'Artist', item.get('track') or 'Track'],
            'fastCopy': metric_support or 'Open charts for the full leaderboard.',
            'primaryHref': reverse('charts'),
            'primaryLabel': 'Open Charts',
            'primaryIcon': 'bar_chart',
            'secondaryHref': reverse('news'),
            'secondaryLabel': 'Read News',
            'secondaryIcon': 'north_east',
        })

    idol_routes = []
    for idx, group in enumerate(list(KPopGroup.objects.filter(rank__isnull=False).order_by('rank', 'name')[:3])):
        _apply_stream_image_to_field(group, 'image_url')
        idol_routes.append({
            'id': _safe_id(group.slug or group.name),
            'kicker': f"Ranked #{group.rank}" if group.rank else 'Featured Group',
            'chip': group.get_group_type_display(),
            'status': group.label or 'Artist',
            'tagline': _shorten_text(group.description or '', 96) or 'Artist profile, members, and fandom context.',
            'title': group.name,
            'copy': _shorten_text(group.description or '', 180) or f"Open {group.name} for profile details, members, and related artist coverage.",
            'image': _optimize_home_image_url(group.image_url, width=1400, height=1400),
            'tags': [group.label or 'Label', group.get_group_type_display(), f"Members {group.members.count()}"],
            'primaryHref': reverse('idol_page', args=[group.slug]),
            'primaryLabel': 'Open Profile',
            'primaryIcon': 'arrow_outward',
            'secondaryHref': reverse('fan_clubs'),
            'secondaryLabel': 'View Fan Clubs',
            'secondaryIcon': 'groups',
        })
    idol_stats = {
        'acts': KPopGroup.objects.count(),
        'members': KPopMember.objects.count(),
        'clubs': FanClubMembership.objects.values('group_id').distinct().count(),
    }

    news_articles = list(BlogArticle.objects.order_by('-created_at')[:4])
    for article in news_articles:
        _apply_stream_images_to_article(article)

    live_track_image = _optimize_home_image_url(getattr(live_track, 'album_art', ''), width=1400, height=1400) if live_track else ''
    live_track_ai = _normalize_live_ai_payload((live_track.live_ai_payload or {}) if live_track else {}, live_track) if live_track else {}
    live_panel = {
        'eyebrow': 'Live Right Now',
        'studio_label': schedule_context['slot'].playlist.name if schedule_context and schedule_context.get('slot') else 'K-Beats Live',
        'status': 'On Air' if live_track else 'Live',
        'tagline': _shorten_text((live_track_ai or {}).get('commentary') or '', 110) if live_track else 'Join the live player and see what is on now.',
        'title': live_track.title if live_track else 'K-Beats Live',
        'description': _shorten_text(((live_track_ai or {}).get('rich_context') or {}).get('profile_body') or '', 180) if live_track else 'Open the live player for the current track and next-up schedule.',
        'chips': [
            f"Now Playing: {live_track.title}" if live_track else 'Live feed active',
            listeners_label,
            f"Up next: {live_programming[1]['title']}" if len(live_programming) > 1 else 'Schedule available',
        ],
        'image': live_track_image,
        'track_title': live_track.title if live_track else 'K-Beats Live',
        'track_artist': live_track.artist if live_track else 'On Air',
        'audience': listeners_label,
        'vibe': str(schedule_context['slot'].genre or 'Live').strip().title() if schedule_context and schedule_context.get('slot') else 'Live',
    }

    comeback_primary = upcoming_releases[0] if upcoming_releases else None
    comeback_cards = []
    for idx, release in enumerate(upcoming_releases[:3]):
        date_label = str(release.get('date_str') or '')
        delta_label = ''
        try:
            release_date = datetime.strptime(date_label, '%Y-%m-%d').date()
            day_delta = (release_date - now_local.date()).days
            delta_label = f"{max(day_delta, 0):02d}"
        except Exception:
            delta_label = '--'
        comeback_cards.append({
            'countdown': delta_label,
            'status': 'Most anticipated' if idx == 0 else ('Closing soon' if idx == 1 else 'On radar'),
            'title': release.get('artist') or release.get('title') or 'Upcoming release',
            'subtitle': release.get('type') or 'Release',
            'description': _shorten_text(release.get('title') or '', 80) or 'Upcoming release on the K-Beats calendar.',
            'href': reverse('comeback_timeline'),
        })

    news_panel = {
        'featured': news_articles[0] if news_articles else None,
        'items': news_articles[1:3] if len(news_articles) > 1 else [],
        'total_count': len(news_articles),
    }

    games_panel = {
        'promo_line': '9 games. Infinite replays.',
        'items': [
            {
                'id': 'beat-streak',
                'title': 'Beat Streak',
                'family': 'Rhythm',
                'views': ['arcade', 'challenge'],
                'status': 'Featured',
                'summary': 'Tap through tempo spikes and chase a perfect streak.',
                'description': 'A rhythm-first sprint with escalating pace, cleaner timing windows, and immediate replay pull.',
                'href': reverse('beat_streak'),
                'icon': 'speed',
                'accentRgb': '0, 240, 255',
                'secondaryRgb': '244, 37, 192',
                'eyebrow': 'Rhythm Run',
                'metric': '5x streak',
                'metric_note': 'Precision wins',
                'tags': ['Rhythm', 'Streak', 'Solo'],
            },
            {
                'id': 'chart-clash',
                'title': 'Chart Clash',
                'family': 'Duel',
                'views': ['challenge', 'knowledge'],
                'status': 'Head To Head',
                'summary': 'Pick the track that charted higher and keep the run alive.',
                'description': 'A fast comparison game built around chart instinct, bragging rights, and tight round-to-round momentum.',
                'href': reverse('chart_clash_promo'),
                'icon': 'trending_up',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '0, 240, 255',
                'eyebrow': 'Chart Duel',
                'metric': '10 rounds',
                'metric_note': 'Multiplier pressure',
                'tags': ['Charts', 'Versus', 'Quick'],
            },
            {
                'id': 'draft-day',
                'title': 'Draft Day',
                'family': 'Strategy',
                'views': ['party', 'challenge'],
                'status': 'Build Your Lineup',
                'summary': 'Assemble your dream roster without blowing the budget.',
                'description': 'A strategy-led draft where fan instinct meets trade-offs, caps, and lineup flex.',
                'href': reverse('draft_day'),
                'icon': 'stars',
                'accentRgb': '0, 240, 255',
                'secondaryRgb': '255, 255, 255',
                'eyebrow': 'Lineup Builder',
                'metric': 'Budget cap',
                'metric_note': 'Every pick matters',
                'tags': ['Strategy', 'Roster', 'Replayable'],
            },
            {
                'id': 'song-game',
                'title': 'Song Game',
                'family': 'Party',
                'views': ['party', 'arcade'],
                'status': 'Fast Start',
                'summary': 'Jump into a simple track-first challenge built for quick sessions.',
                'description': 'The easiest way to start playing fast without setup friction or deep rules.',
                'href': reverse('song_game'),
                'icon': 'videogame_asset',
                'accentRgb': '255, 255, 255',
                'secondaryRgb': '0, 240, 255',
                'eyebrow': 'Instant Play',
                'metric': 'Quick rounds',
                'metric_note': 'Low friction',
                'tags': ['Party', 'Quick', 'Accessible'],
            },
            {
                'id': 'idol-scramble',
                'title': 'Idol Scramble',
                'family': 'Puzzle',
                'views': ['knowledge', 'challenge'],
                'status': 'Brain Teaser',
                'summary': 'Unscramble idols and groups before the clock wins.',
                'description': 'A puzzle-style challenge that rewards fan memory, speed, and clean recognition.',
                'href': reverse('idol_scramble'),
                'icon': 'extension',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '255, 255, 255',
                'eyebrow': 'Puzzle Board',
                'metric': 'Timed solve',
                'metric_note': 'Memory + pace',
                'tags': ['Puzzle', 'Idols', 'Timed'],
            },
            {
                'id': 'lyric-drop',
                'title': 'Lyric Drop',
                'family': 'Lyrics',
                'views': ['knowledge', 'party'],
                'status': 'Sing It Back',
                'summary': 'Finish the lyric before the next clue lands.',
                'description': 'A lyric-led challenge designed for fans who know hooks, verses, and instant callbacks.',
                'href': reverse('lyric_drop'),
                'icon': 'lyrics',
                'accentRgb': '0, 240, 255',
                'secondaryRgb': '244, 37, 192',
                'eyebrow': 'Lyric Test',
                'metric': 'Hook recall',
                'metric_note': 'Fan memory flex',
                'tags': ['Lyrics', 'Party', 'Recognition'],
            },
            {
                'id': 'bias-selector',
                'title': 'Bias Selector',
                'family': 'Discovery',
                'views': ['party', 'knowledge'],
                'status': 'Fan Favourite',
                'summary': 'Follow the prompts and see where your bias lands.',
                'description': 'A lighter discovery route that feels social, shareable, and easy to replay with friends.',
                'href': reverse('bias_selector'),
                'icon': 'favorite',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '0, 240, 255',
                'eyebrow': 'Bias Match',
                'metric': 'Share ready',
                'metric_note': 'Low-pressure fun',
                'tags': ['Discovery', 'Social', 'Fan'],
            },
            {
                'id': 'fandom-trivia',
                'title': 'Fandom Trivia',
                'family': 'Quiz',
                'views': ['knowledge', 'challenge'],
                'status': 'Deep Cut',
                'summary': 'Test what you know about fandoms, labels, and group history.',
                'description': 'The strongest pure-knowledge lane for fans who want bragging rights, not just quick reflexes.',
                'href': reverse('fandom_trivia'),
                'icon': 'quiz',
                'accentRgb': '255, 255, 255',
                'secondaryRgb': '244, 37, 192',
                'eyebrow': 'Knowledge Check',
                'metric': 'Lore heavy',
                'metric_note': 'True fan mode',
                'tags': ['Quiz', 'Lore', 'Knowledge'],
            },
            {
                'id': 'mv-matcher',
                'title': 'MV Matcher',
                'family': 'Visual',
                'views': ['arcade', 'party'],
                'status': 'Frame Hunt',
                'summary': 'Identify the act from a single video frame.',
                'description': 'A fast visual challenge built around iconic shots, styling cues, and instant pattern recognition.',
                'href': reverse('mv_matcher'),
                'icon': 'movie',
                'accentRgb': '0, 240, 255',
                'secondaryRgb': '255, 255, 255',
                'eyebrow': 'Visual Match',
                'metric': 'One frame',
                'metric_note': 'Spot it fast',
                'tags': ['Visual', 'MV', 'Quick'],
            },
        ],
    }

    shop_panel = {
        'promo_line': 'Limited drops, collector picks, and merch built for the fandom.',
        'benefits': [
            {'title': 'Free Shipping', 'copy': 'On orders over £75 worldwide.', 'icon': 'local_shipping'},
            {'title': 'Limited Drops', 'copy': 'Small-run pieces that feel collectible, not generic.', 'icon': 'diamond'},
            {'title': 'Fast Dispatch', 'copy': 'Quick ship windows for in-stock fan essentials.', 'icon': 'bolt'},
        ],
        'items': [
            {
                'id': 'spectrum-collection',
                'title': 'Spectrum Collection',
                'family': 'Featured Drop',
                'views': ['drops', 'collectors'],
                'status': 'Limited Edition',
                'summary': 'The official numbered drop with premium streetwear energy.',
                'description': 'A flagship collection that gives the Shop menu a real event feel instead of a flat merch tray.',
                'href': reverse('shop'),
                'icon': 'diamond',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '0, 240, 255',
                'eyebrow': 'Featured Drop',
                'price': '£89.00',
                'comparePrice': '£120.00',
                'tags': ['Limited', 'Numbered', 'Streetwear'],
            },
            {
                'id': 'neon-logo-hoodie',
                'title': 'Neon Logo Hoodie',
                'family': 'Apparel',
                'views': ['essentials', 'collectors'],
                'status': 'Best Seller',
                'summary': 'Heavyweight layer with the core K-Beats wordmark front and centre.',
                'description': 'A dependable flagship piece for fans who want the cleanest branded look first.',
                'href': reverse('shop'),
                'icon': 'checkroom',
                'accentRgb': '255, 255, 255',
                'secondaryRgb': '244, 37, 192',
                'eyebrow': 'Wardrobe Core',
                'price': '£79.00',
                'comparePrice': '',
                'tags': ['Apparel', 'Core', 'In Stock'],
            },
            {
                'id': 'spectrum-oversized-tee',
                'title': 'Spectrum Oversized Tee',
                'family': 'Apparel',
                'views': ['drops', 'essentials'],
                'status': 'Sale',
                'summary': 'Oversized fit with drop energy and brighter colour contrast.',
                'description': 'The easiest entry point into the current collection without losing the limited-drop mood.',
                'href': reverse('shop'),
                'icon': 'styler',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '255, 255, 255',
                'eyebrow': 'Drop Layer',
                'price': '£39.00',
                'comparePrice': '£55.00',
                'tags': ['Drop', 'Apparel', 'Sale'],
            },
            {
                'id': 'rock-star-album',
                'title': 'Stray Kids - ROCK-STAR',
                'family': 'Albums',
                'views': ['collectors', 'essentials'],
                'status': 'Collector Pick',
                'summary': 'A strong album lane for fans who want music-first shelf pieces.',
                'description': 'Collectors mode should spotlight display-worthy picks, not only apparel.',
                'href': reverse('shop'),
                'icon': 'album',
                'accentRgb': '0, 240, 255',
                'secondaryRgb': '255, 255, 255',
                'eyebrow': 'Shelf Ready',
                'price': '£34.99',
                'comparePrice': '',
                'tags': ['Album', 'Collector', 'Display'],
            },
            {
                'id': 'army-bomb',
                'title': 'Official ARMY Bomb Ver.4',
                'family': 'Lightsticks',
                'views': ['collectors', 'essentials'],
                'status': 'High Demand',
                'summary': 'One of the clearest collector-led hero products in the current range.',
                'description': 'A premium fandom item that gives the panel an unmistakable merch destination feel.',
                'href': reverse('shop'),
                'icon': 'flare',
                'accentRgb': '0, 240, 255',
                'secondaryRgb': '244, 37, 192',
                'eyebrow': 'Fandom Gear',
                'price': '£59.99',
                'comparePrice': '',
                'tags': ['Lightstick', 'Collector', 'Premium'],
            },
            {
                'id': 'newjeans-poster',
                'title': 'NewJeans - Get Up Poster',
                'family': 'Posters',
                'views': ['drops', 'collectors'],
                'status': 'Wall Ready',
                'summary': 'A lower-price collector entry that still feels display-driven.',
                'description': 'Posters give the Shop menu a quick-pick lane for fans not ready to commit to bigger pieces.',
                'href': reverse('shop'),
                'icon': 'photo',
                'accentRgb': '255, 255, 255',
                'secondaryRgb': '0, 240, 255',
                'eyebrow': 'Print Drop',
                'price': '£24.99',
                'comparePrice': '',
                'tags': ['Poster', 'Display', 'Accessible'],
            },
            {
                'id': 'photocard-binder',
                'title': 'Photocard Binder Set',
                'family': 'Accessories',
                'views': ['essentials', 'collectors'],
                'status': 'Utility Pick',
                'summary': 'Storage-first merch for fans who care about collecting without clutter.',
                'description': 'A practical accessory lane that makes the Shop feel more resourceful than pure apparel.',
                'href': reverse('shop'),
                'icon': 'folder_copy',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '0, 240, 255',
                'eyebrow': 'Collector Utility',
                'price': '£19.99',
                'comparePrice': '',
                'tags': ['Accessories', 'Organise', 'Everyday'],
            },
            {
                'id': 'blink-lightstick',
                'title': 'BLINK Official Lightstick',
                'family': 'Lightsticks',
                'views': ['collectors', 'drops'],
                'status': 'Fan Signal',
                'summary': 'An instantly recognisable fandom piece with high display value.',
                'description': 'Another strong collector route that keeps the panel feeling broad, not single-brand.',
                'href': reverse('shop'),
                'icon': 'celebration',
                'accentRgb': '244, 37, 192',
                'secondaryRgb': '255, 255, 255',
                'eyebrow': 'Signal Piece',
                'price': '£54.99',
                'comparePrice': '',
                'tags': ['Lightstick', 'Display', 'Fan Gear'],
            },
        ],
    }
    recent_request_count = SongRequest.objects.count()

    return {
        'mega_menu_streams': stream_cards,
        'mega_menu_charts': rankings,
        'mega_menu_idols': idol_routes,
        'mega_menu_idol_stats': idol_stats,
        'mega_menu_live': live_panel,
        'mega_menu_schedule': live_programming[:2],
        'mega_menu_comebacks_primary': comeback_primary,
        'mega_menu_comebacks': comeback_cards,
        'mega_menu_news': news_panel,
        'mega_menu_games': games_panel,
        'mega_menu_shop': shop_panel,
        'mega_menu_last_chart_sync': ranking_obj.created_at if ranking_obj else None,
        'mega_menu_request_count': recent_request_count,
    }


def _serialize_header_mega_menu_payload(context):
    now_local = timezone.localtime()

    def _relative_time_label(value):
        if not value:
            return 'Updated recently'
        delta = now_local - timezone.localtime(value)
        total_seconds = max(int(delta.total_seconds()), 0)
        if total_seconds < 60:
            return 'Updated just now'
        total_minutes = total_seconds // 60
        if total_minutes < 60:
            return f'Updated {total_minutes}m ago'
        total_hours = total_minutes // 60
        if total_hours < 24:
            return f'Updated {total_hours}h ago'
        total_days = total_hours // 24
        return f'Updated {total_days}d ago'

    def _serialize_article(article):
        if not article:
            return None
        return {
            'slug': article.slug,
            'title': article.title,
            'subtitle': article.subtitle or article.source_title or '',
            'category': article.category or 'News',
            'source_name': article.source_name or '',
            'reading_time': article.reading_time,
            'image': getattr(article, 'image', '') or '',
            'created_at': article.created_at.isoformat() if article.created_at else None,
            'created_at_label': _relative_time_label(article.created_at),
        }

    news_panel = context.get('mega_menu_news') or {}
    featured_article = _serialize_article(news_panel.get('featured'))
    items = [_serialize_article(article) for article in news_panel.get('items') or [] if article]

    return {
        'streams': context.get('mega_menu_streams') or [],
        'charts': context.get('mega_menu_charts') or [],
        'idols': context.get('mega_menu_idols') or [],
        'idol_stats': context.get('mega_menu_idol_stats') or {},
        'live': context.get('mega_menu_live') or {},
        'schedule': context.get('mega_menu_schedule') or [],
        'comebacks_primary': context.get('mega_menu_comebacks_primary') or {},
        'comebacks': context.get('mega_menu_comebacks') or [],
        'news': {
            'featured': featured_article,
            'items': items,
            'total_count': news_panel.get('total_count') or len(items) + (1 if featured_article else 0),
        },
        'games': context.get('mega_menu_games') or {},
        'shop': context.get('mega_menu_shop') or {},
        'last_chart_sync': context.get('mega_menu_last_chart_sync').isoformat() if context.get('mega_menu_last_chart_sync') else None,
        'request_count': context.get('mega_menu_request_count') or 0,
        'generated_at': now_local.isoformat(),
    }


def header_mega_menu_lab(request):
    context = _build_header_mega_menu_context(request)
    payload = _serialize_header_mega_menu_payload(context)
    context.update({
        'mega_menu_streams_json': payload['streams'],
        'mega_menu_charts_json': payload['charts'],
        'mega_menu_idols_json': payload['idols'],
        'mega_menu_live_json': payload['live'],
        'mega_menu_schedule_json': payload['schedule'],
        'mega_menu_news_json': payload['news'],
        'mega_menu_games_json': payload['games'],
        'mega_menu_shop_json': payload['shop'],
        'mega_menu_comebacks_primary_json': payload['comebacks_primary'],
        'mega_menu_comebacks_json': payload['comebacks'],
        'mega_menu_idol_stats_json': payload['idol_stats'],
        'mega_menu_request_count_json': payload['request_count'],
        'mega_menu_last_chart_sync_json': payload['last_chart_sync'],
    })
    return render(request, 'core/header_mega_menu_lab.html', context)


def api_header_mega_menu_data(request):
    context = _build_header_mega_menu_context(request)
    return JsonResponse({
        'ok': True,
        'payload': _serialize_header_mega_menu_payload(context),
    })


def charts(request):
    chart_type = request.GET.get('type', 'songs')
    
    # Map 'songs' to 'daily' for now as that's our main track chart
    db_type = 'daily' if chart_type == 'songs' else chart_type
    
    ranking_obj = Ranking.objects.filter(timeframe=db_type).first()
    raw_rankings = ranking_obj.ranking_data if ranking_obj else []
    last_updated = ranking_obj.created_at if ranking_obj else None
    
    rankings = []
    for idx, item in enumerate(raw_rankings):
        img_url = item.get('artwork_url')
        if not img_url:
            img_url = f"https://api.dicebear.com/7.x/initials/svg?seed={item.get('artist')}&backgroundColor=f425c0"
        
        trend_raw = item.get('trend')
        if trend_raw and trend_raw != '-' and trend_raw != 'Stable':
            if '+' in trend_raw or 'â–²' in trend_raw:
                trend_icon = 'â–²'
                trend_class = 'text-primary'
                trend_value = ''.join(filter(str.isdigit, trend_raw))
            elif '-' in trend_raw or 'â–¼' in trend_raw:
                trend_icon = 'â–¼'
                trend_class = 'text-slate-500'
                trend_value = ''.join(filter(str.isdigit, trend_raw))
            else:
                trend_icon = '-'
                trend_class = 'text-slate-500'
                trend_value = ''
        else:
            trend_icon = '-'
            trend_class = 'text-slate-500'
            trend_value = ''
        
        rankings.append({
            'rank': idx + 1,
            'artist': item.get('artist'),
            'title': item.get('track'),
            'image': img_url,
            'trend_icon': trend_icon,
            'trend_class': trend_class,
            'trend_value': trend_value,
            'metric_support': item.get('primary_metric_support', ''),
        })
    
    chart_types = [
        {'key': 'songs', 'label': 'Daily', 'db': 'daily'},
        {'key': 'weekly', 'label': 'Weekly', 'db': 'weekly'},
        {'key': 'monthly', 'label': 'Monthly', 'db': 'monthly'},
        {'key': 'soloists', 'label': 'Solo Artists', 'db': 'soloists'},
        {'key': 'groups', 'label': 'Idol Groups', 'db': 'groups'},
    ]

    ranking_methodology = [
        'Digital impact carries the highest weight (streaming and chart velocity).',
        'Music-show performance and sustained momentum are included.',
        'Global fandom signals (voting and sales activity) are included.',
        'Trends show movement since the previous sync window.',
    ]

    if db_type == 'daily':
        ranking_sources = [
            {'name': 'iChart', 'detail': 'Hourly synced real-time ranking feed for daily chart positions.'},
        ]
        ranking_explain_label = 'Daily chart uses direct iChart sync.'
    else:
        ranking_sources = [
            {'name': 'Circle Chart / MelOn / Spotify KR / YouTube Music', 'detail': 'Digital impact source set used in synthesis prompts.'},
            {'name': 'Music Shows', 'detail': 'M Countdown, Music Bank, Inkigayo signals are included.'},
            {'name': 'Voting and Sales', 'detail': 'Fandom and sales indicators are considered for momentum.'},
        ]
        ranking_explain_label = 'This timeframe uses weighted synthesis from multiple source families.'
    
    # Separate #1 track, main chart (2-10), and ticker (11-20)
    number_one = rankings[0] if rankings else None
    chart_main = rankings[1:10] if len(rankings) > 1 else []
    chart_ticker = rankings[10:20] if len(rankings) > 10 else []
    
    context = {
        'rankings': rankings,
        'number_one': number_one,
        'chart_main': chart_main,
        'chart_ticker': chart_ticker,
        'current_type': chart_type,
        'chart_types': chart_types,
        'last_updated': last_updated,
        'ranking_methodology': ranking_methodology,
        'ranking_sources': ranking_sources,
        'ranking_explain_label': ranking_explain_label,
    }
    return render(request, 'core/charts.html', context)

def idols(request):
    now = timezone.now()
    data_obj = ComebackData.objects.filter(year=now.year, month=now.month).first()
    today_str = now.strftime('%Y-%m-%d')
    
    today_events = []
    if data_obj and today_str in data_obj.data:
        day_data = data_obj.data[today_str]
        for b in day_data.get('birthdays', []):
            today_events.append({'type': 'Birthday', 'name': b.get('name'), 'group': b.get('group')})

    group_type = request.GET.get('type')
    gender = request.GET.get('gender')
    
    groups = KPopGroup.objects.all()
    
    if group_type == 'solo':
        groups = groups.filter(group_type='SOLO')
    elif group_type == 'groups':
        groups = groups.exclude(group_type='SOLO')
        
    if gender == 'male':
        groups = groups.filter(models.Q(group_type='BOY') | models.Q(group_type='SOLO')) 
        # Note: Ideally gender would be a separate field, but using group_type for now
    elif gender == 'female':
        groups = groups.filter(models.Q(group_type='GIRL') | models.Q(group_type='SOLO'))

    groups = list(groups.filter(rank__isnull=False).order_by('rank', 'name'))
    for group in groups:
        _apply_stream_image_to_field(group, 'image_url')
    
    return render(request, 'core/idols.html', {
        'today_events': today_events, 
        'groups': groups,
        'selected_type': group_type,
        'selected_gender': gender
    })


def stray_kids(request):
    now = timezone.now()
    group_name = "Stray Kids"
    members = ["Bang Chan", "Lee Know", "Changbin", "Hyunjin", "Han", "Felix", "Seungmin", "I.N"]
    
    # Fetch events for current and next month
    months = [
        (now.year, now.month),
        (now.year if now.month < 12 else now.year + 1, now.month + 1 if now.month < 12 else 1)
    ]
    
    upcoming_events = []
    latest_releases = []
    
    for y, m in months:
        data_obj = ComebackData.objects.filter(year=y, month=m).first()
        if data_obj:
            for date_key, day_data in data_obj.data.items():
                
                # Filter Anniversaries
                for a in day_data.get('anniversaries', []):
                    if group_name.lower() in a.get('group', '').lower():
                        upcoming_events.append({
                            'date': date_key,
                            'type': 'Anniversary',
                            'title': f"{group_name} Debut Anniversary",
                            'is_today': (date_key == now.strftime('%Y-%m-%d'))
                        })
                
                # Filter Releases
                for r in day_data.get('releases', []):
                    if group_name.lower() in r.get('artist', '').lower():
                        latest_releases.append({
                            'date': date_key,
                            'title': r.get('title'),
                            'image': r.get('image'),
                            'type': r.get('type')
                        })

    # Sort and filter (upcoming only for events, all for releases)
    today_str = now.strftime('%Y-%m-%d')
    upcoming_events = [e for e in upcoming_events if e['date'] >= today_str]
    upcoming_events.sort(key=lambda x: x['date'])
    latest_releases.sort(key=lambda x: x['date'], reverse=True)

    context = {
        'upcoming_events': upcoming_events[:5],
        'latest_releases': latest_releases[:10]
    }
    return render(request, 'core/stray_kids.html', context)

def idol_universe(request):
    return render(request, 'core/idol_universe.html')

def schedule(request):
    return render(request, 'core/schedule.html')

def profile(request):
    return render(request, 'core/profile.html')

_news_cache = {'articles': [], 'ts': 0}

def news(request):
    all_blog_qs = BlogArticle.objects.order_by('-created_at')
    all_blog = list(all_blog_qs)
    for article in all_blog:
        _apply_stream_images_to_article(article)

    featured = all_blog[0] if all_blog else None
    remaining = all_blog[1:] if len(all_blog) > 1 else []

    cats = list(
        all_blog_qs.order_by()
        .values_list('category', flat=True)
        .distinct()
    )

    return render(request, 'core/news.html', {
        'featured': featured,
        'articles': remaining,
        'all_articles': all_blog,
        'categories': cats,
        'total_count': len(all_blog),
    })


def _fetch_kpop_news():
    import re
    import time
    import xml.etree.ElementTree as ET
    from datetime import datetime
    from difflib import SequenceMatcher

    now = time.time()
    if _news_cache['articles'] and (now - _news_cache['ts'] < 1800):
        return _news_cache['articles']

    IMAGES = {
        'Comeback': 'https://images.unsplash.com/photo-1493225255756-d9584f8606e9?auto=format&fit=crop&q=80&w=800',
        'Charts': 'https://images.unsplash.com/photo-1514525253361-bee8a48740d0?auto=format&fit=crop&q=80&w=800',
        'Tour': 'https://images.unsplash.com/photo-1540039155733-5bb30b53aa14?auto=format&fit=crop&q=80&w=800',
        'Awards': 'https://images.unsplash.com/photo-1532452119098-a3650b3c46d3?auto=format&fit=crop&q=80&w=800',
        'Industry': 'https://images.unsplash.com/photo-1526218626217-dc65a29bb444?auto=format&fit=crop&q=80&w=800',
        'News': 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&q=80&w=800',
    }

    def _cat(title):
        t = title.lower()
        if any(w in t for w in [
            'comeback', 'debut', 'release', 'album', 'single',
            'mv', 'teaser', 'tracklist', 'ep',
        ]):
            return 'Comeback'
        if any(w in t for w in [
            'chart', 'billboard', 'melon', '#1', 'no.1',
            'record', 'million', 'views', 'sales',
        ]):
            return 'Charts'
        if any(w in t for w in [
            'tour', 'concert', 'fan meeting', 'fanmeet',
            'world tour', 'show',
        ]):
            return 'Tour'
        if any(w in t for w in [
            'award', 'mama', 'mma', 'daesang', 'win',
            'nomination',
        ]):
            return 'Awards'
        if any(w in t for w in [
            'dating', 'enlist', 'military', 'contract',
            'agency', 'lawsuit', 'renew',
        ]):
            return 'Industry'
        return 'News'

    def _is_duplicate_title(new_title, seen_titles, threshold=0.70):
        """Return True if new_title is too similar to any already-seen title."""
        nt = new_title.lower()
        for existing in seen_titles:
            ratio = SequenceMatcher(None, nt, existing.lower()).ratio()
            if ratio >= threshold:
                return True
        return False

    # Keywords that confirm K-pop relevance
    KPOP_SIGNALS = [
        'k-pop', 'kpop', 'idol', 'girl group', 'boy group',
        'debut', 'comeback', 'mv ', ' mv', 'music video',
        'album', 'single', 'ep ', ' ep', 'mini album',
        'melon', 'gaon', 'hanteo', 'billboard', 'chart',
        'concert', 'world tour', 'fan meeting', 'lightstick',
        'fandom', 'trainee', 'sm entertainment', 'jyp', 'yg entertainment',
        'hybe', 'starship', 'cube entertainment', 'pledis',
        'bts', 'blackpink', 'twice', 'stray kids', 'aespa', 'ive',
        'newjeans', 'seventeen', 'nct', 'exo', 'got7', 'shinee',
        'bigbang', '2ne1', 'winner', 'ikon', 'monsta x', 'day6',
        'txt', 'enhypen', 'itzy', 'red velvet', 'mamamoo', 'apink',
        'ateez', 'the boyz', 'p1harmony', 'xdinary heroes', 'zerobaseone',
        'illit', 'kiss of life', 'lesserafim', 'le sserafim', 'gidle',
        '(g)i-dle', 'kep1er', 'nmixx', 'young k', 'super junior',
        'solo artist', 'rapper', 'soloist',
    ]

    # Keywords that indicate K-drama / general celebrity gossip - not K-pop
    DRAMA_EXCLUSIONS = [
        'drama recap', 'episode recap', 'k-drama', 'kdrama',
        'drama review', 'drama cast', 'drama series', 'drama premiere',
        'drama rating', 'webtoon adaptation', 'netflix series',
        'disney+ series', ' ep 1', ' ep 2', ' ep 3', ' ep 4',
        'jtbc drama', 'tvn drama', 'mbc drama', 'kbs drama',
        'sbs drama', 'ocn drama', 'tving drama',
        'series finale', 'season finale', 'maintains steady ratings',
        'ahead of series', 'ratings ahead', 'upcoming drama',
        'drama viewer', 'drama special', 'drama script',
    ]

    def _is_kpop_article(title, categories):
        """Return True only if the item is genuinely K-pop related."""
        combined = (title + ' ' + ' '.join(categories)).lower()

        # Hard exclude drama/gossip content
        if any(excl in combined for excl in DRAMA_EXCLUSIONS):
            return False

        # Must have at least one positive K-pop signal
        return any(sig in combined for sig in KPOP_SIGNALS)

    # Direct RSS feeds from authoritative K-pop outlets
    feeds = [
        ('https://soompi.com/feed', 'Soompi'),
        ('https://koreaboo.com/feed', 'Koreaboo'),
        ('https://seoulbeats.com/feed/', 'Seoulbeats'),
        ('https://thebiaslist.com/feed/', 'The Bias List'),
    ]

    articles = []
    seen_titles = []

    for url, source_name in feeds:
        try:
            resp = requests.get(
                url, timeout=10,
                headers={'User-Agent': 'K-Beats/1.0'},
            )
            if resp.status_code != 200:
                logger.warning("[RSS] %s returned HTTP %s", source_name, resp.status_code)
                continue

            root = ET.fromstring(resp.content)
            for item in root.iter('item'):
                title = (item.findtext('title') or '').strip()
                if not title:
                    continue

                # K-pop relevance filter - skip drama recaps and non-kpop content
                categories = [
                    c.text for c in item.findall('category') if c.text
                ]
                if not _is_kpop_article(title, categories):
                    logger.info("[RSS] Skipping non-kpop: %r", title)
                    continue

                # Cross-feed duplicate check - skip if very similar title already collected
                if _is_duplicate_title(title, seen_titles):
                    logger.info("[RSS] Skipping near-duplicate: %r", title)
                    continue

                link = item.findtext('link', '')
                pub_date = item.findtext('pubDate', '')
                desc = item.findtext('description', '')

                img = None
                m = re.search(
                    r'<img[^>]+src=["\']([^"\']+)["\']',
                    desc or '',
                )
                if m:
                    img = m.group(1)

                date_str = ''
                time_ago = ''
                if pub_date:
                    try:
                        dt = datetime.strptime(
                            pub_date,
                            '%a, %d %b %Y %H:%M:%S %Z',
                        )
                        date_str = dt.strftime('%b %d, %Y')
                        delta = datetime.utcnow() - dt
                        hrs = int(delta.total_seconds() // 3600)
                        if hrs < 1:
                            time_ago = 'Just now'
                        elif hrs < 24:
                            time_ago = f'{hrs}h ago'
                        else:
                            time_ago = f'{hrs // 24}d ago'
                    except Exception:
                        date_str = pub_date[:16]

                cat = _cat(title)
                if not img:
                    img = IMAGES.get(cat, IMAGES['News'])

                clean = re.sub(r'<[^>]+>', '', desc or '')
                excerpt = clean[:180].strip()
                if len(clean) > 180:
                    excerpt += '...'

                articles.append({
                    'title': title,
                    'source': source_name,
                    'link': link,
                    'date': date_str,
                    'time_ago': time_ago,
                    'category': cat,
                    'excerpt': excerpt,
                    'image': img,
                })
                seen_titles.append(title)

        except Exception as e:
            logger.warning("[RSS] Failed fetching %s: %s", source_name, e)

    if not articles:
        articles = [
            {
                'category': 'Comeback',
                'title': "BLACKPINK's Lisa Announces Global Fan-Meet Tour",
                'excerpt': "The 'Lalisa' star is set to hit 12 cities across"
                           " Asia and Europe starting next month.",
                'date': 'Mar 06, 2026',
                'time_ago': '1d ago',
                'source': 'Soompi',
                'link': '#',
                'image': IMAGES['Tour'],
            },
            {
                'category': 'Charts',
                'title': "Stray Kids 'ATE' Remains #1 on World Albums",
                'excerpt': "The group continues their dominant streak on"
                           " global charts for the 5th consecutive week.",
                'date': 'Mar 05, 2026',
                'time_ago': '2d ago',
                'source': 'Billboard',
                'link': '#',
                'image': IMAGES['Charts'],
            },
            {
                'category': 'Comeback',
                'title': "LE SSERAFIM Drops Teaser for Upcoming Comeback",
                'excerpt': "Fearless as ever, the group prepares for a"
                           " massive Q2 comeback with a cinematic teaser.",
                'date': 'Mar 04, 2026',
                'time_ago': '3d ago',
                'source': 'AllKPop',
                'link': '#',
                'image': IMAGES['Comeback'],
            },
            {
                'category': 'Awards',
                'title': "BTS Jimin Wins Artist of the Year at Global"
                         " Music Awards",
                'excerpt': "The solo star took home the top prize at the"
                           " ceremony held in Los Angeles.",
                'date': 'Mar 03, 2026',
                'time_ago': '4d ago',
                'source': 'Koreaboo',
                'link': '#',
                'image': IMAGES['Awards'],
            },
            {
                'category': 'Tour',
                'title': "SEVENTEEN Announces 'Right Here' World Tour"
                         " Extension",
                'excerpt': "10 new cities added including London, Paris,"
                           " and SÃ£o Paulo for the 2026 leg.",
                'date': 'Mar 02, 2026',
                'time_ago': '5d ago',
                'source': 'Soompi',
                'link': '#',
                'image': IMAGES['Tour'],
            },
            {
                'category': 'Industry',
                'title': "HYBE and SM Entertainment Announce Joint Venture",
                'excerpt': "The two largest K-Pop agencies reveal a"
                           " groundbreaking content partnership.",
                'date': 'Mar 01, 2026',
                'time_ago': '6d ago',
                'source': 'Korea Herald',
                'link': '#',
                'image': IMAGES['Industry'],
            },
        ]

    _news_cache['articles'] = articles
    _news_cache['ts'] = now
    return articles[:40]


def shop(request):
    return render(request, 'core/shop.html')

def pricing(request):
    return render(request, 'core/pricing.html')

def about_us(request):
    return render(request, 'core/about_us.html')

def coming_soon(request):
    return render(request, 'core/coming_soon.html')

def games(request):
    return render(request, 'core/games.html')


def _build_404_context(request):
    requested_path = urllib.parse.unquote(request.get_full_path() or '/')
    if len(requested_path) > 72:
        requested_path = f"{requested_path[:69]}..."

    previous_path = ''
    referrer = str(request.META.get('HTTP_REFERER') or '').strip()
    if referrer:
        parsed_referrer = urllib.parse.urlparse(referrer)
        if parsed_referrer.netloc == request.get_host():
            previous_path = parsed_referrer.path or reverse('home')
            if parsed_referrer.query:
                previous_path = f"{previous_path}?{parsed_referrer.query}"
            if previous_path == request.get_full_path():
                previous_path = reverse('home')

    featured_links = [
        {
            'eyebrow': 'On air now',
            'title': 'Live Radio',
            'description': 'Jump back into the station and keep the music going.',
            'url': reverse('live'),
            'icon': 'radio',
        },
        {
            'eyebrow': 'Keep listening',
            'title': 'Stream Hub',
            'description': 'Open the player and pick up where the broadcast left off.',
            'url': reverse('stream_hub'),
            'icon': 'play_circle',
        },
        {
            'eyebrow': 'Fan pulse',
            'title': 'Charts',
            'description': 'See what is rising, holding, and making noise right now.',
            'url': reverse('charts'),
            'icon': 'leaderboard',
        },
    ]
    secondary_links = [
        {
            'title': 'Idols',
            'description': 'Browse artists, groups, and fandom favourites.',
            'url': reverse('idols'),
            'icon': 'groups_2',
        },
        {
            'title': 'Games',
            'description': 'Switch lanes and play one of the K-Beats fan games.',
            'url': reverse('games'),
            'icon': 'sports_esports',
        },
        {
            'title': 'News',
            'description': 'Catch up on comebacks, stories, and fresh headlines.',
            'url': reverse('news'),
            'icon': 'article',
        },
        {
            'title': 'Get the App',
            'description': 'Head to the app page for the full K-Beats experience.',
            'url': reverse('promo'),
            'icon': 'phone_iphone',
        },
    ]

    return {
        'requested_path': requested_path,
        'previous_path': previous_path,
        'featured_links': featured_links,
        'secondary_links': secondary_links,
    }


def preview_404(request):
    return render(request, 'core/404.html', _build_404_context(request))


def custom_404(request, exception):
    context = _build_404_context(request)
    return render(request, 'core/404.html', context, status=404)

@csrf_exempt
@require_POST
def prelaunch_signup(request):
    from .models import PreLaunchSignup
    from django.db import IntegrityError
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        age = data.get('age')
        if not name or not email or not age:
            return JsonResponse({'ok': False, 'error': 'All fields are required.'}, status=400)
        age = int(age)
        if age < 5 or age > 120:
            return JsonResponse({'ok': False, 'error': 'Please enter a valid age.'}, status=400)
        PreLaunchSignup.objects.create(name=name, email=email, age=age)
        return JsonResponse({'ok': True})
    except IntegrityError:
        return JsonResponse({'ok': False, 'error': 'This email is already signed up!'})
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'Invalid data.'}, status=400)


@csrf_exempt
@require_POST
def email_promotion_signup(request):
    from django.db import IntegrityError
    from .models import EmailPromotionSignup

    try:
        data = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid request payload.'}, status=400)

    email = str(data.get('email', '')).strip().lower()
    source = str(data.get('source', 'homepage_newsletter')).strip() or 'homepage_newsletter'

    if not email:
        return JsonResponse({'ok': False, 'error': 'Please enter your email address.'}, status=400)

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'ok': False, 'error': 'Please enter a valid email address.'}, status=400)

    try:
        EmailPromotionSignup.objects.create(email=email, source=source)
    except IntegrityError:
        return JsonResponse({'ok': False, 'error': 'This email is already subscribed.'}, status=409)

    return JsonResponse({'ok': True, 'message': 'Thanks! You are subscribed.'})

def signups_login_view(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('signups_dashboard')
    error = ''
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            user_obj = None
        if user_obj:
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None and user.is_staff:
                login(request, user)
                return redirect('signups_dashboard')
            elif user is not None:
                error = 'You do not have staff access.'
            else:
                error = 'Invalid email or password.'
        else:
            error = 'Invalid email or password.'
    return render(request, 'core/signups_login.html', {'error': error})

@login_required(login_url='/staff/login/')
def signups_dashboard_view(request):
    if not request.user.is_staff:
        return redirect('signups_login')
    from .models import PreLaunchSignup
    from django.db.models import Avg
    from datetime import timedelta
    now = timezone.now()
    signups = PreLaunchSignup.objects.all()
    total = signups.count()
    today_count = signups.filter(signed_up_at__date=now.date()).count()
    week_count = signups.filter(signed_up_at__gte=now - timedelta(days=7)).count()
    avg_age = signups.aggregate(avg=Avg('age'))['avg']
    avg_age = round(avg_age) if avg_age else 0
    return render(request, 'core/signups_dashboard.html', {
        'signups': signups,
        'total': total,
        'today_count': today_count,
        'week_count': week_count,
        'avg_age': avg_age,
    })

@login_required(login_url='/staff/login/')
def signups_export_view(request):
    if not request.user.is_staff:
        return redirect('signups_login')
    import csv
    from django.http import HttpResponse
    from .models import PreLaunchSignup
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="kbeats_signups.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Email', 'Age', 'Signed Up'])
    for s in PreLaunchSignup.objects.all():
        writer.writerow([s.name, s.email, s.age, s.signed_up_at.strftime('%Y-%m-%d %H:%M')])
    return response

def signups_logout_view(request):
    logout(request)
    return redirect('signups_login')

def presenters(request):
    return render(request, 'core/presenters.html')

def achievement_popup(request):
    return render(request, 'core/achievement_popup.html')

def login_page(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = ''
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        # Look up user by email
        try:
            user_obj = User.objects.get(email=email)
            username = user_obj.username
        except User.DoesNotExist:
            username = None
        if username:
            user = authenticate(
                request, username=username, password=password
            )
            if user is not None:
                login(request, user)
                profile, _ = UserProfile.objects.get_or_create(user=user)
                if not profile.onboarding_completed:
                    return redirect('my_station_onboarding')
                nxt = request.GET.get('next', 'dashboard')
                return redirect(nxt)
            else:
                error = 'Invalid email or password.'
        else:
            error = 'Invalid email or password.'
    return render(request, 'core/login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('home')


def promo(request):
    return render(request, 'core/promo.html')


def listen_free_landing(request):
    up_next_tracks = []
    artist_marquee = ['BTS', 'Stray Kids', 'ATEEZ', 'ENHYPEN', 'TWICE', 'LE SSERAFIM', 'SEVENTEEN', 'aespa']
    try:
        state, _ = RadioStationState.objects.get_or_create(id=1)
        state = _auto_rotate_station(state)
        listener_count = int(state.listeners_count or 3847)
        current_track = state.current_track
        up_next_ids = list(state.up_next or [])[:3]
        raw_up_next_tracks = list(RadioTrack.objects.filter(id__in=up_next_ids))
        raw_up_next_tracks = [
            track for track in raw_up_next_tracks
            if track and not _is_generated_voice_track(track)
        ]
        raw_up_next_tracks.sort(key=lambda track: up_next_ids.index(track.id) if track.id in up_next_ids else 999)
        raw_up_next = raw_up_next_tracks[:3]

        up_next_tracks = [
            {
                'title': track.title,
                'artist': track.artist,
                'album_art': _coalesce_stream_image_url(track.album_art),
            }
            for track in raw_up_next
        ]
    except DatabaseError:
        state = None
        current_track = None
        listener_count = 3847

    preview_track = {
        'title': current_track.title if current_track else 'K-Beats Live',
        'artist': current_track.artist if current_track else 'Always on for K-pop fans',
        'album_art': _coalesce_stream_image_url(
            current_track.album_art if current_track else '',
        ),
        'audio_url': (
            _build_stream_audio_url(current_track.audio_url)
            if current_track and current_track.audio_url
            else ''
        ),
    }

    feature_sections = [
        {
            'eyebrow': 'Always live',
            'title': 'The Beat Never Stops.',
            'body': 'Go from your feed to full K-pop in seconds. No app to install, no account needed -- just tap play and you are live.',
            'bullets': [
                'One tap and you are streaming',
                'See what is playing and what is coming up next',
                'Built for headphones, commutes, and late-night K-pop sessions',
            ],
            'visual': 'live',
        },
        {
            'eyebrow': 'Always fresh',
            'title': 'Stay Ahead of Every Comeback.',
            'body': 'K-pop moves fast. Our weekly charts and new release tracker keep you in the loop before it blows up on your timeline.',
            'bullets': [
                'Weekly chart updates so you never miss a rise',
                'Discover new drops without the doom-scroll',
                'Stay connected to the fandom, not just the music',
            ],
            'visual': 'charts',
        },
        {
            'eyebrow': 'Fan-first',
            'title': 'Your Fandom Has A Home.',
            'body': 'Join fan club spaces built around your favourites. Follow your bias group, get alerts for comebacks, and connect with fans who get it.',
            'bullets': [
                'Dedicated spaces for your favourite groups',
                'Comeback alerts so you are never the last to know',
                'A station that feels like a fan community, not just a music player',
            ],
            'visual': 'community',
        },
        {
            'eyebrow': 'Level up',
            'title': 'Go Ad-Free. Get More. It Is Free To Try.',
            'body': 'Free gets you in the door. VIP takes the experience further -- no ads, priority song requests, and early access to comeback drops. Try it free for 3 days, no card needed.',
            'bullets': [
                '3 days free -- cancel anytime, no strings',
                'Stream without interruption, request your favourite tracks',
                'Fan-first extras that actually make a difference',
            ],
            'visual': 'vip',
        },
    ]

    comparison_rows = [
        {'label': '24/7 live K-pop radio', 'free': True, 'vip': True},
        {'label': 'Charts and rankings', 'free': True, 'vip': True},
        {'label': 'Fan clubs and community', 'free': True, 'vip': True},
        {'label': 'Ad-free listening', 'free': False, 'vip': True},
        {'label': 'Priority song requests', 'free': False, 'vip': True},
        {'label': 'Early comeback alerts', 'free': False, 'vip': True},
    ]

    fan_quotes = [
        {
            'name': 'Mia, London',
            'initials': 'ML',
            'quote': 'I came for one song and stayed for two hours. K-Beats actually gets what K-pop fans want -- it is addictive.',
        },
        {
            'name': 'Jordan, Manchester',
            'initials': 'JM',
            'quote': 'Charts, comebacks, live radio -- all in one place. I have ditched three other apps since I found K-Beats.',
        },
        {
            'name': 'Ari, Birmingham',
            'initials': 'AB',
            'quote': 'I started on the free stream and upgraded to VIP within a week. The ad-free listening alone is worth it for a K-pop obsessive like me.',
        },
    ]

    idol_images = []
    try:
        for artist_name in artist_marquee:
            group = (
                KPopGroup.objects.filter(name__iexact=artist_name).first()
                or KPopGroup.objects.filter(name__icontains=artist_name).order_by('rank', 'name').first()
            )
            if not group:
                continue
            _apply_stream_image_to_field(group, 'image_url')
            image_url = _coalesce_stream_image_url(group.image_url, fallback='')
            if not image_url:
                continue
            idol_images.append({
                'name': group.name,
                'image_url': image_url,
            })
            if len(idol_images) >= 3:
                break
    except DatabaseError:
        idol_images = []

    context = {
        'seo_title': 'Listen Free to Live K-Pop 24/7 | K-Beats Radio',
        'seo_description': 'Stream live K-pop in seconds on K-Beats Radio. No app, no card, just 24/7 hits, charts, fan clubs, and a free 3-day VIP trial when you want more.',
        'seo_type': 'website',
        'seo_image': preview_track['album_art'],
        'seo_image_alt': f"Listen free to K-Beats Radio live K-pop stream featuring {preview_track['title']}",
        'extra_schema_json': json.dumps({
            '@context': 'https://schema.org',
            '@type': 'RadioStation',
            'name': 'K-Beats Radio',
            'url': request.build_absolute_uri(reverse('listen_free_landing')),
            'description': 'Stream live K-pop 24/7 on K-Beats Radio, a UK-based station for fans across the country and around the world.',
            'genre': ['K-pop', 'Pop Music', 'Internet Radio'],
            'areaServed': 'Worldwide',
            'inLanguage': 'en',
            'sameAs': [
                request.build_absolute_uri(reverse('live')),
                request.build_absolute_uri(reverse('charts')),
                request.build_absolute_uri(reverse('fan_clubs')),
            ],
        }),
        'listener_count': listener_count,
        'preview_track': preview_track,
        'image_fallback_url': DEFAULT_STREAM_IMAGE_URL,
        'up_next_tracks': up_next_tracks,
        'idol_images': idol_images,
        'vip_trial_url': f"{reverse('pricing')}#compare-plans",
        'listen_live_url': reverse('live'),
        'artist_marquee': artist_marquee,
        'feature_sections': feature_sections,
        'comparison_rows': comparison_rows,
        'fan_quotes': fan_quotes,
    }
    return render(request, 'core/listen_free_landing.html', context)


def chart_clash_promo(request):
    daily_rank = Ranking.objects.filter(timeframe='daily').first()
    tracks = []
    if daily_rank and daily_rank.ranking_data:
        for item in daily_rank.ranking_data:
            if item.get('artwork_url') and item.get('track') and item.get('artist'):
                tracks.append({
                    'title': item['track'],
                    'artist': item['artist'],
                    'rank': item.get('rank', '?'),
                    'image': item['artwork_url'],
                })
            if len(tracks) >= 2:
                break
    return render(request, 'core/chart_clash_promo.html', {
        'track_a': tracks[0] if len(tracks) > 0 else None,
        'track_b': tracks[1] if len(tracks) > 1 else None,
    })


def bias_selector_promo(request):
    featured_artists = list(
        KPopGroup.objects.filter(
            rank__isnull=False
        ).exclude(
            image_url=''
        ).order_by('rank')[:3]
    )
    hero_artists = []
    for artist in featured_artists:
        hero_artists.append({
            'id': artist.id,
            'name': artist.name,
            'slug': artist.slug,
            'image_url': artist.image_url,
            'rank': artist.rank,
            'label': artist.label or 'K-Pop',
            'group_type': artist.get_group_type_display(),
            'member_count': artist.members.count(),
        })

    social_image = hero_artists[0]['image_url'] if hero_artists else ''
    extra_schema_json = json.dumps({
        "@context": "https://schema.org",
        "@type": "VideoGame",
        "name": "Bias Selector",
        "url": request.build_absolute_uri(reverse('bias_selector')),
        "description": (
            "Take the Bias Selector quiz on K-Beats to discover your K-Pop bias "
            "through audio picks, visual choices, and fan-personality prompts."
        ),
        "genre": ["Music", "Quiz", "Personality"],
        "playMode": "SinglePlayer",
        "applicationCategory": "Game",
        "publisher": {
            "@type": "Organization",
            "name": "K-Beats",
        },
    })

    return render(request, 'core/bias_selector_promo.html', {
        'hero_artists': hero_artists,
        'hero_artist_primary': hero_artists[0] if len(hero_artists) > 0 else None,
        'hero_artist_secondary': hero_artists[1] if len(hero_artists) > 1 else None,
        'hero_artist_tertiary': hero_artists[2] if len(hero_artists) > 2 else None,
        'seo_title': 'Bias Selector - Find Your K-Pop Bias Match | K-Beats Games',
        'seo_description': (
            'Bias Selector is K-Beats\' interactive K-Pop personality quiz. '
            'Compare vibes, answer fan prompts, and discover the idol or group '
            'that matches your energy.'
        ),
        'seo_image': social_image,
        'seo_image_alt': 'Bias Selector promo artwork on K-Beats',
        'extra_schema_json': extra_schema_json,
    })


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    error = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        if not username or not email or not password:
            error = 'All fields are required.'
        elif password != password2:
            error = 'Passwords do not match.'
        elif len(password) < 8:
            error = 'Password must be at least 8 characters.'
        elif User.objects.filter(username=username).exists():
            error = 'Username is already taken.'
        elif User.objects.filter(email=email).exists():
            error = 'An account with this email already exists.'
        else:
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
            login(request, user)
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if not profile.onboarding_completed:
                return redirect('my_station_onboarding')
            return redirect('dashboard')
    return render(request, 'core/signup.html', {'error': error})


@login_required
def dashboard(request):
    now = timezone.now()
    today_str = now.strftime('%Y-%m-%d')
    user = request.user

    # Ensure profile exists
    profile, _ = UserProfile.objects.get_or_create(user=user)
    onboarding_redirect = _maybe_redirect_to_onboarding(request, profile)
    if onboarding_redirect:
        return onboarding_redirect

    progression = _run_progression_unlocks(user)

    # Time-aware greeting
    hour = now.hour
    if hour < 12:
        greeting = 'Good Morning'
    elif hour < 18:
        greeting = 'Good Afternoon'
    else:
        greeting = 'Good Evening'

    # Bias data
    bias = profile.bias
    bias_members = []
    bias_comebacks = []
    if bias:
        bias_members = list(bias.members.all()[:6])
        # Bias comebacks from ComebackData
        y, m = now.year, now.month
        for _ in range(3):
            cb = ComebackData.objects.filter(
                year=y, month=m
            ).first()
            if cb:
                for dk, day in cb.data.items():
                    for r in day.get('releases', []):
                        art = (r.get('artist') or '').lower()
                        ttl = (r.get('title') or '').lower()
                        bn = bias.name.lower()
                        if bn in art or bn in ttl:
                            r['date_str'] = dk
                            bias_comebacks.append(r)
            m += 1
            if m > 12:
                m, y = 1, y + 1
        bias_comebacks.sort(key=lambda x: x['date_str'])
        bias_comebacks = bias_comebacks[:4]

    # Favourites
    favourites = list(
        FavouriteSong.objects.filter(user=user)[:8]
    )

    # All artists (for bias selector)
    from django.db.models import Count
    all_artists = list(
        KPopGroup.objects.order_by('name').values_list(
            'id', 'name', 'image_url', 'group_type'
        )
    )

    # Hot pick artists - top 20 most chosen as bias
    hot_pick_ids = list(
        KPopGroup.objects.annotate(
            bias_count=Count('biased_by')
        ).order_by('-bias_count', 'name')[:20].values_list('id', flat=True)
    )

    # Trending tracks (top 5)
    daily_rank = Ranking.objects.filter(
        timeframe='daily'
    ).first()
    trending = []
    if daily_rank and daily_rank.ranking_data:
        for idx, item in enumerate(
            daily_rank.ranking_data[:5]
        ):
            img = item.get('artwork_url') or (
                "https://api.dicebear.com/7.x/initials/svg"
                f"?seed={item.get('artist')}"
                "&backgroundColor=f425c0"
            )
            trending.append({
                'rank': idx + 1,
                'artist': item.get('artist'),
                'title': item.get('track'),
                'image': img,
            })

    # Upcoming comebacks (next 6)
    upcoming = []
    y, m = now.year, now.month
    months = []
    for _ in range(3):
        months.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    for cb_y, cb_m in months:
        cb_obj = ComebackData.objects.filter(
            year=cb_y, month=cb_m
        ).first()
        if not cb_obj:
            continue
        for date_key, day in cb_obj.data.items():
            if date_key >= today_str:
                for r in day.get('releases', []):
                    r['date_str'] = date_key
                    upcoming.append(r)
    upcoming.sort(key=lambda x: x['date_str'])
    upcoming = upcoming[:6]

    # Latest articles
    articles = list(
        BlogArticle.objects.order_by('-created_at')[:4]
    )

    # Top artists
    top_artists = list(
        KPopGroup.objects.filter(
            rank__isnull=False
        ).order_by('rank')[:8]
    )

    # Stats - mix platform + personal
    stats = {
        'total_artists': KPopGroup.objects.count(),
        'total_favourites': FavouriteSong.objects.filter(
            user=user
        ).count(),
        'total_tracks': sum(
            len(r.ranking_data or [])
            for r in Ranking.objects.all()[:6]
        ),
        'upcoming_count': len(upcoming),
        'member_since': user.date_joined,
    }

    # Game scores
    game_scores = list(
        GameScore.objects.filter(user=user)[:10]
    )
    best_score = (
        GameScore.objects.filter(user=user)
        .order_by('-score')
        .first()
    )

    week_cutoff = now - timedelta(days=7)
    weekly_stream_total = RadioTrackPlay.objects.filter(
        user=user,
        listened_at__gte=week_cutoff,
    ).count()
    weekly_top_streams = list(
        RadioTrackPlay.objects.filter(
            user=user,
            listened_at__gte=week_cutoff,
        )
        .values('track__title', 'track__artist', 'track__album_art')
        .annotate(
            play_count=models.Count('id'),
            last_listened=models.Max('listened_at'),
        )
        .order_by('-play_count', '-last_listened')[:5]
    )

    today = timezone.localdate()
    radio_today_count = RadioTrackPlay.objects.filter(
        user=user,
        listened_at__date=today,
    ).count()
    games_today_qs = GameScore.objects.filter(
        user=user,
        played_at__date=today,
    )
    games_today_count = games_today_qs.count()
    high_score_today = games_today_qs.filter(score__gte=70).exists()

    daily_quests = [
        {
            'key': 'radio_3',
            'label': 'Listen to 3 live tracks',
            'progress': min(radio_today_count, 3),
            'target': 3,
            'completed': radio_today_count >= 3,
        },
        {
            'key': 'game_1',
            'label': 'Play 1 game',
            'progress': min(games_today_count, 1),
            'target': 1,
            'completed': games_today_count >= 1,
        },
        {
            'key': 'score_70',
            'label': 'Score 70+ in any game',
            'progress': 1 if high_score_today else 0,
            'target': 1,
            'completed': high_score_today,
        },
    ]

    streak_milestones = [
        {'days': 3, 'label': '3-day streak', 'unlocked': progression.get('current_streak', 0) >= 3},
        {'days': 7, 'label': '7-day streak', 'unlocked': progression.get('current_streak', 0) >= 7},
        {'days': 14, 'label': '14-day streak', 'unlocked': progression.get('current_streak', 0) >= 14},
    ]

    badges = list(user.badges.all())

    return render(request, 'core/dashboard.html', {
        'trending': trending,
        'upcoming': upcoming,
        'articles': articles,
        'top_artists': top_artists,
        'stats': stats,
        'current_month': now.strftime('%B %Y'),
        'greeting': greeting,
        'profile': profile,
        'bias': bias,
        'bias_members': bias_members,
        'bias_comebacks': bias_comebacks,
        'favourites': favourites,
        'all_artists': all_artists,
        'hot_pick_ids': hot_pick_ids,
        'total_favourites': stats['total_favourites'],
        'game_scores': game_scores,
        'best_score': best_score,
        'all_contests': list(Contest.objects.all()) if request.user.is_staff else [],
        'my_fan_clubs': list(
            FanClubMembership.objects.filter(
                user=user
            ).select_related('group')[:8]
        ),
        'badges': badges,
        'weekly_stream_total': weekly_stream_total,
        'weekly_top_streams': weekly_top_streams,
        'weekly_stream_range_label': f"{week_cutoff.strftime('%d %b')} - {now.strftime('%d %b')}",
        'daily_quests': daily_quests,
        'daily_quests_completed': sum(1 for quest in daily_quests if quest['completed']),
        'current_activity_streak': progression.get('current_streak', 0),
        'longest_activity_streak': progression.get('longest_streak', 0),
        'streak_milestones': streak_milestones,
    })


@login_required
@require_POST
def set_bias(request):
    """Set or clear the user's bias artist."""
    # Accept both form-encoded and JSON bodies
    artist_id = request.POST.get('artist_id')
    if not artist_id:
        try:
            body = json.loads(request.body)
            artist_id = body.get('artist_id')
        except (json.JSONDecodeError, AttributeError):
            pass
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user
    )
    if artist_id:
        try:
            group = KPopGroup.objects.get(pk=int(artist_id))
            profile.bias = group
            profile.save()
            return JsonResponse({
                'ok': True,
                'name': group.name,
                'image': group.image_url or '',
            })
        except (KPopGroup.DoesNotExist, ValueError):
            return JsonResponse(
                {'ok': False, 'error': 'Artist not found'},
                status=404,
            )
    else:
        profile.bias = None
        profile.save()
        return JsonResponse({'ok': True, 'name': None})


@login_required
@require_http_methods(["GET"])
def api_live_chat_messages(request):
    messages_qs = LiveChatMessage.objects.select_related('user').order_by('-created_at')[:50]
    messages = []
    for item in reversed(list(messages_qs)):
        messages.append({
            'id': item.id,
            'username': item.user.username,
            'message': item.message,
            'created_at': item.created_at.isoformat(),
            'is_me': item.user_id == request.user.id,
        })
    return JsonResponse({'ok': True, 'messages': messages})


def _contains_blocked_chat_language(raw_text):
    text = str(raw_text or '').lower().strip()
    if not text:
        return False

    leet_map = str.maketrans({
        '@': 'a',
        '$': 's',
        '0': 'o',
        '1': 'i',
        '3': 'e',
        '4': 'a',
        '5': 's',
        '7': 't',
        '!': 'i',
    })
    normalized = text.translate(leet_map)
    tokenized = re.sub(r'[^a-z\s]', ' ', normalized)
    compact = re.sub(r'[^a-z]', '', normalized)

    blocked_terms = {
        'fuck', 'fucking', 'shit', 'bitch', 'asshole', 'bastard',
        'dick', 'pussy', 'cunt', 'whore', 'slut', 'motherfucker',
        'fag', 'retard', 'idiot',
    }

    try:
        db_terms = ChatBlockedTerm.objects.filter(is_active=True).values_list('term', flat=True)
        for term in db_terms:
            cleaned = str(term or '').strip().lower()
            if cleaned:
                blocked_terms.add(cleaned)
    except Exception:
        pass

    words = [w for w in tokenized.split() if w]
    for word in words:
        if word in blocked_terms:
            return True

    for term in blocked_terms:
        if term in compact:
            return True

    return False


@login_required
@require_POST
def api_live_chat_send(request):
    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    text = (payload.get('message') or '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Message is empty.'}, status=400)

    if _contains_blocked_chat_language(text):
        return JsonResponse(
            {'ok': False, 'error': 'Message rejected: offensive language is not allowed.'},
            status=400,
        )

    text = text[:500]
    chat_item = LiveChatMessage.objects.create(user=request.user, message=text)
    return JsonResponse({
        'ok': True,
        'message': {
            'id': chat_item.id,
            'username': request.user.username,
            'message': chat_item.message,
            'created_at': chat_item.created_at.isoformat(),
            'is_me': True,
        }
    })


@login_required
@require_POST
def toggle_favourite(request):
    """Add or remove a song from favourites."""
    title = request.POST.get('title', '').strip()
    artist = request.POST.get('artist', '').strip()
    if not title or not artist:
        return JsonResponse(
            {'ok': False, 'error': 'Missing title/artist'},
            status=400,
        )
    fav, created = FavouriteSong.objects.get_or_create(
        user=request.user,
        title=title,
        artist=artist,
        defaults={
            'artwork_url': request.POST.get(
                'artwork_url', ''
            ),
            'preview_url': request.POST.get(
                'preview_url', ''
            ),
            'itunes_url': request.POST.get(
                'itunes_url', ''
            ),
        },
    )
    if not created:
        fav.delete()
    return JsonResponse({
        'ok': True,
        'added': created,
        'title': title,
        'artist': artist,
    })


@login_required
@require_POST
def save_this_moment(request):
    """Save the currently playing moment as a favourite song (idempotent add)."""
    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    track_id_raw = payload.get('track_id')
    title = str(payload.get('title') or '').strip()
    artist = str(payload.get('artist') or '').strip()
    artwork_url = str(payload.get('artwork_url') or '').strip()
    audio_url = str(payload.get('audio_url') or '').strip()

    track = None
    try:
        track_id = int(track_id_raw or 0)
    except (TypeError, ValueError):
        track_id = 0

    if track_id > 0:
        track = RadioTrack.objects.filter(id=track_id).first()

    if track:
        title = (track.title or '').strip() or title
        artist = (track.artist or '').strip() or artist
        artwork_url = (track.album_art or '').strip() or artwork_url
        audio_url = (track.audio_url or '').strip() or audio_url

    if not title or not artist:
        state = RadioStationState.objects.select_related('current_track').filter(id=1).first()
        live_track = state.current_track if state else None
        if live_track:
            title = (live_track.title or '').strip() or title
            artist = (live_track.artist or '').strip() or artist
            artwork_url = (live_track.album_art or '').strip() or artwork_url
            audio_url = (live_track.audio_url or '').strip() or audio_url

    if not title or not artist:
        return JsonResponse({'ok': False, 'error': 'No current track to save.'}, status=400)

    fav, created = FavouriteSong.objects.get_or_create(
        user=request.user,
        title=title,
        artist=artist,
        defaults={
            'artwork_url': artwork_url,
            'preview_url': audio_url,
            'itunes_url': '/live/',
        },
    )

    changed = False
    if artwork_url and fav.artwork_url != artwork_url:
        fav.artwork_url = artwork_url
        changed = True
    if audio_url and fav.preview_url != audio_url:
        fav.preview_url = audio_url
        changed = True
    if changed:
        fav.save(update_fields=['artwork_url', 'preview_url'])

    return JsonResponse({
        'ok': True,
        'saved': True,
        'already_saved': not created,
        'title': title,
        'artist': artist,
    })


@login_required
def remove_favourite(request, pk):
    """Remove a specific favourite song."""
    if request.method == 'POST':
        FavouriteSong.objects.filter(
            pk=pk, user=request.user
        ).delete()
    return redirect('dashboard')


def request_track(request):
    if request.method == 'POST':
        song_title = request.POST.get('song_title', '').strip()[:300]
        artist = request.POST.get('artist', '').strip()[:200]
        listener_name = request.POST.get('listener_name', '').strip()[:100]
        message = request.POST.get('message', '').strip()[:500]
        if song_title and artist:
            SongRequest.objects.create(
                song_title=song_title,
                artist=artist,
                listener_name=listener_name,
                message=message,
            )
            return JsonResponse({'success': True})
        return JsonResponse(
            {'success': False, 'error': 'Missing fields'},
            status=400,
        )

    groups = KPopGroup.objects.order_by('name')
    groups_json = json.dumps([
        {'slug': g.slug, 'name': g.name}
        for g in groups
    ])
    recent_requests = SongRequest.objects.all()[:10]
    return render(request, 'core/request_track.html', {
        'groups': groups,
        'groups_json': groups_json,
        'recent_requests': recent_requests,
    })


def api_group_songs(request, slug):
    """Return songs from iTunes for a given KPopGroup slug."""
    import urllib.request
    import urllib.parse

    group = KPopGroup.objects.filter(slug=slug).first()
    if not group:
        return JsonResponse({'songs': []})

    ITUNES_NAME_MAP = {
        '(G)I-DLE': 'G I-DLE',
    }
    itunes_term = ITUNES_NAME_MAP.get(group.name, group.name)
    encoded = urllib.parse.quote_plus(itunes_term)
    url = (
        f"https://itunes.apple.com/search?term={encoded}"
        f"&entity=song&attribute=artistTerm&limit=50"
    )
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0'}
    )
    songs = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            for item in data.get('results', []):
                songs.append(item.get('trackName', ''))
    except Exception:
        pass

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in songs:
        if s and s not in seen:
            seen.add(s)
            unique.append(s)

    return JsonResponse({'songs': unique})


@login_required
@require_POST
def save_game_score(request):
    """Save a game score from the song game."""
    try:
        data = json.loads(request.body)
        GameScore.objects.create(
            user=request.user,
            game=data.get('game', 'song_game'),
            score=int(data.get('score', 0)),
            correct=int(data.get('correct', 0)),
            total=int(data.get('total', 0)),
            best_streak=int(data.get('best_streak', 0)),
        )
        _run_progression_unlocks(request.user)
        return JsonResponse({'ok': True})
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'ok': False}, status=400)

def idol_scramble(request):
    names = []
    for g in KPopGroup.objects.all()[:60]:
        hint = f"{g.get_group_type_display()} - {g.label}"
        names.append({'name': g.name, 'hint': hint})
    for m in KPopMember.objects.select_related('group').all()[:60]:
        hint = f"Member of {m.group.name}"
        sn = m.stage_name or m.name
        names.append({'name': sn, 'hint': hint})
    return render(request, 'core/idol_scramble.html', {
        'scramble_names_json': json.dumps(names),
    })


def lyric_drop(request):
    return render(request, 'core/lyric_drop.html')

def fandom_trivia(request):
    import random
    groups = list(KPopGroup.objects.exclude(label='').all())
    if not groups:
        return redirect('games')
    
    all_labels = list(set(g.label for g in groups if g.label))
    type_choices = ['Boy Group', 'Girl Group', 'Soloist']

    questions = []
    # Mix of questions: Labels, Member Counts, Group Types
    for g in random.sample(groups, min(len(groups), 20)):
        q_type = random.choice(['type', 'label', 'count'])
        if q_type == 'type':
            answer = g.get_group_type_display()
            wrong = [t for t in type_choices if t != answer]
            opts = [answer] + random.sample(wrong, min(3, len(wrong)))
            random.shuffle(opts)
            questions.append({
                'question': f"What type of artist is {g.name}?",
                'answer': answer,
                'options': opts,
            })
        elif q_type == 'label' and g.label:
            wrong_labels = [l for l in all_labels if l != g.label]
            if len(wrong_labels) < 3:
                continue
            opts = [g.label] + random.sample(wrong_labels, 3)
            random.shuffle(opts)
            questions.append({
                'question': f"Which label is {g.name} signed to?",
                'answer': g.label,
                'options': opts,
            })
        else:
            count = g.members.count()
            if count > 0:
                wrong = list(set([str(count+1), str(max(1, count-1)), str(random.randint(1, 13))]) - {str(count)})
                opts = [str(count)] + random.sample(wrong, min(3, len(wrong)))
                random.shuffle(opts)
                questions.append({
                    'question': f"How many members are in {g.name}?",
                    'answer': str(count),
                    'options': opts,
                })

    random.shuffle(questions)
    return render(request, 'core/fandom_trivia.html', {
        'questions_json': json.dumps(questions[:10]),
    })

def mv_matcher(request):
    import random
    members = list(KPopMember.objects.select_related('group').exclude(image_url=''))
    groups = list(KPopGroup.objects.exclude(image_url=''))
    
    rounds = []
    # Mix members and groups
    pool = []
    for m in members:
        pool.append({'image': m.image_url, 'answer': m.stage_name or m.name, 'hint': f"Member of {m.group.name}"})
    for g in groups:
        pool.append({'image': g.image_url, 'answer': g.name, 'hint': f"{g.get_group_type_display()} Group"})

    if len(pool) < 10:
        return redirect('dashboard') # Not enough data

    selected = random.sample(pool, min(len(pool), 15))
    for item in selected:
        # Generate 3 wrong options
        others = [x['answer'] for x in pool if x['answer'] != item['answer']]
        options = random.sample(list(set(others)), 3) + [item['answer']]
        random.shuffle(options)
        rounds.append({
            'image': item['image'],
            'answer': item['answer'],
            'hint': item['hint'],
            'options': options
        })

    return render(request, 'core/mv_matcher.html', {
        'rounds_json': json.dumps(rounds[:10]),
    })

def draft_day(request):
    import random
    members = list(KPopMember.objects.select_related('group').order_by('group__name', 'name'))
    if not members:
        return redirect('games')

    pool = []
    for m in members:
        # Seed by member name so stats/cost are consistent across refreshes
        rng = random.Random(m.name)
        pool.append({
            'name': m.stage_name or m.name,
            'group': m.group.name,
            'image': m.image_url or (m.group.image_url if m.group.image_url else ''),
            'stats': {
                'vocal': rng.randint(70, 99),
                'dance': rng.randint(70, 99),
                'rap': rng.randint(60, 99),
                'visual': rng.randint(80, 99),
            },
            'cost': rng.randint(10, 50)
        })
        
    return render(request, 'core/draft_day.html', {
        'draft_pool_json': json.dumps(pool),
    })

def beat_streak(request):
    import random
    import urllib.request
    import urllib.parse
    from .models import GameScore, KPopGroup

    daily_rank = Ranking.objects.filter(timeframe='daily').first()
    tracks = []
    if daily_rank and daily_rank.ranking_data:
        for item in daily_rank.ranking_data[:50]:
            tracks.append({
                'artist': item.get('artist', ''),
                'title': item.get('track', ''),
                'artwork_url': item.get('artwork_url', ''),
            })

    # Pick tracks with previews
    random.shuffle(tracks)
    game_tracks = []
    # Poll up to 30 tracks to ensure we have enough for a random grid + rotation
    for t in tracks:
        if len(game_tracks) >= 30: break
        try:
            q = urllib.parse.quote(f"{t['artist']} {t['title']}")
            url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                results = data.get('results', [])
                if results:
                    t['preview_url'] = results[0].get('previewUrl', '')
                    if not t['artwork_url']:
                        t['artwork_url'] = results[0].get('artworkUrl100', '').replace('100x100bb', '600x600bb')
                    
                    # Try to get group info
                    group = KPopGroup.objects.filter(name__icontains=t['artist']).first()
                    if group:
                        t['group_desc'] = group.description[:200] + '...' if group.description else ''
                        t['group_image'] = group.image_url
                    else:
                        t['group_desc'] = "K-Pop sensation taking the charts by storm."
                        t['group_image'] = t['artwork_url']
                    
                    game_tracks.append(t)
        except:
            continue
    
    # Shuffle AGAIN before sending to ensure the grid is truly random every time
    random.shuffle(game_tracks)

    high_scores = GameScore.objects.filter(game='beat_streak').order_by('-score')[:10]

    return render(request, 'core/beat_streak.html', {
        'game_tracks_json': json.dumps(game_tracks),
        'high_scores': high_scores,
    })


def beat_streak_v2(request):
    """Beat Streak v2 - same data pipeline, upgraded template."""
    import random
    import urllib.request
    import urllib.parse
    from .models import GameScore, KPopGroup

    daily_rank = Ranking.objects.filter(timeframe='daily').first()
    tracks = []
    if daily_rank and daily_rank.ranking_data:
        for item in daily_rank.ranking_data[:50]:
            tracks.append({
                'artist': item.get('artist', ''),
                'title': item.get('track', ''),
                'artwork_url': item.get('artwork_url', ''),
            })

    random.shuffle(tracks)
    game_tracks = []
    for t in tracks:
        if len(game_tracks) >= 30:
            break
        try:
            q = urllib.parse.quote(f"{t['artist']} {t['title']}")
            url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=1"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                results = data.get('results', [])
                if results:
                    t['preview_url'] = results[0].get('previewUrl', '')
                    if not t['artwork_url']:
                        t['artwork_url'] = results[0].get('artworkUrl100', '').replace('100x100bb', '600x600bb')
                    group = KPopGroup.objects.filter(name__icontains=t['artist']).first()
                    if group:
                        t['group_desc'] = group.description[:200] + '...' if group.description else ''
                        t['group_image'] = group.image_url
                    else:
                        t['group_desc'] = "K-Pop sensation taking the charts by storm."
                        t['group_image'] = t['artwork_url']
                    game_tracks.append(t)
        except Exception:
            continue

    random.shuffle(game_tracks)
    high_scores = GameScore.objects.filter(game='beat_streak').order_by('-score')[:10]

    return render(request, 'core/beat_streak_v2.html', {
        'game_tracks_json': json.dumps(game_tracks),
        'high_scores': high_scores,
    })


def chart_clash(request):
    daily_rank = Ranking.objects.filter(
        timeframe='daily'
    ).first()
    tracks = []
    if daily_rank and daily_rank.ranking_data:
        for i, item in enumerate(daily_rank.ranking_data[:30]):
            artist = item.get('artist', '')
            title = item.get('track', '')
            image = item.get('artwork_url', '')
            if not artist or not title:
                continue
            tracks.append({
                'title': title,
                'artist': artist,
                'rank': i + 1,
                'image': image or '',
            })
    return render(request, 'core/chart_clash.html', {
        'chart_tracks_json': json.dumps(tracks),
    })


def song_game(request):
    import random
    import urllib.request
    import urllib.parse

    daily_rank = Ranking.objects.filter(
        timeframe='daily'
    ).first()
    tracks = []
    if daily_rank and daily_rank.ranking_data:
        for item in daily_rank.ranking_data[:40]:
            artist = item.get('artist', '')
            title = item.get('track', '')
            if not artist or not title:
                continue
            tracks.append({
                'artist': artist,
                'title': title,
                'artwork_url': item.get('artwork_url', ''),
            })

    # Enrich tracks with iTunes preview URLs
    for t in tracks:
        try:
            q = urllib.parse.quote(
                f"{t['artist']} {t['title']}"
            )
            url = (
                f"https://itunes.apple.com/search?term={q}"
                "&entity=song&limit=1"
            )
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                results = data.get('results', [])
                if results:
                    t['preview_url'] = results[0].get(
                        'previewUrl', ''
                    )
                    if not t['artwork_url']:
                        t['artwork_url'] = results[0].get(
                            'artworkUrl100', ''
                        ).replace('100x100bb', '600x600bb')
        except Exception:
            pass

    # Keep only tracks that have a preview URL
    tracks = [t for t in tracks if t.get('preview_url')]

    # Shuffle and pick up to 10 rounds
    random.shuffle(tracks)
    game_tracks = tracks[:10]

    return render(request, 'core/song_game.html', {
        'game_tracks_json': json.dumps(game_tracks),
    })

def contests(request):
    all_contests = Contest.objects.filter(is_active=True)
    featured = all_contests.filter(is_featured=True).first()
    if featured:
        grid = all_contests.exclude(pk=featured.pk)
    else:
        grid = all_contests
    return render(request, 'core/contests.html', {
        'featured': featured,
        'grid': grid,
    })


@require_http_methods(["GET", "POST"])
def contest_entry(request, slug):
    contest = get_object_or_404(Contest, slug=slug, is_active=True)
    if request.method == 'POST':
        name = bleach.clean(request.POST.get('name', '').strip(), tags=[], strip=True)
        email = bleach.clean(request.POST.get('email', '').strip(), tags=[], strip=True)
        country = bleach.clean(request.POST.get('country', '').strip(), tags=[], strip=True)
        username = bleach.clean(request.POST.get('username', '').strip(), tags=[], strip=True)
        answer = bleach.clean(request.POST.get('answer', '').strip(), tags=[], strip=True)
        if not name or not email or not answer:
            return JsonResponse({'error': 'Required fields missing.'}, status=400)
        ContestEntry.objects.create(
            contest=contest,
            name=name,
            email=email,
            country=country,
            username=username,
            answer=answer,
        )
        return JsonResponse({'success': True, 'entry_number': contest.entry_count})
    prizes = contest.prizes if isinstance(contest.prizes, list) else []
    rules = [r.strip() for r in contest.rules.splitlines() if r.strip()]
    return render(request, 'core/contest_entry.html', {
        'contest': contest,
        'prizes': prizes,
        'rules': rules,
    })

def _search_all(q):
    """Run search across all content types. Returns dict of results."""
    import urllib.request
    import urllib.parse

    from django.db.models import Q

    artists = list(KPopGroup.objects.filter(name__icontains=q)[:12])
    members = list(
        KPopMember.objects.select_related('group').filter(
            Q(name__icontains=q) | Q(stage_name__icontains=q)
        )[:12]
    )
    articles = list(
        BlogArticle.objects.filter(
            Q(title__icontains=q) | Q(subtitle__icontains=q)
        )[:12]
    )

    # Songs from ranking data
    songs = []
    for r in Ranking.objects.all()[:6]:
        for item in (r.ranking_data or []):
            track = item.get('track', '')
            artist = item.get('artist', '')
            if q.lower() in track.lower() or q.lower() in artist.lower():
                art = item.get('artwork_url', '')
                if not art:
                    art = f"https://api.dicebear.com/7.x/initials/svg?seed={artist}&backgroundColor=f425c0"
                songs.append({
                    'title': track,
                    'artist': artist,
                    'image': art,
                })
    seen_songs = set()
    unique_songs = []
    for s in songs:
        key = (s['title'].lower(), s['artist'].lower())
        if key not in seen_songs:
            seen_songs.add(key)
            unique_songs.append(s)
    songs = unique_songs[:12]

    # Albums & tracks from iTunes
    itunes_albums = []
    itunes_tracks = []
    try:
        encoded = urllib.parse.quote_plus(q)
        url = (
            f"https://itunes.apple.com/search?term={encoded}"
            f"&entity=album&attribute=artistTerm&limit=8&genreId=51"
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            for item in json.loads(resp.read().decode()).get('results', []):
                art = item.get('artworkUrl100', '').replace('100x100bb', '600x600bb')
                artist_name = item.get('artistName', '')
                # Try to resolve a local KPopGroup slug so we can link to album_detail
                group_match = KPopGroup.objects.filter(
                    name__iexact=artist_name
                ).first() or KPopGroup.objects.filter(
                    name__icontains=artist_name.split('(')[0].strip()
                ).first()
                itunes_albums.append({
                    'title': item.get('collectionName', ''),
                    'artist': artist_name,
                    'image': art,
                    'track_count': item.get('trackCount', 0),
                    'collection_id': item.get('collectionId', ''),
                    'slug': group_match.slug if group_match else '',
                    'itunes_url': item.get('collectionViewUrl', ''),
                })
    except Exception:
        pass

    try:
        encoded = urllib.parse.quote_plus(q)
        url = (
            f"https://itunes.apple.com/search?term={encoded}"
            f"&entity=song&attribute=artistTerm&limit=10&genreId=51"
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            for item in json.loads(resp.read().decode()).get('results', []):
                art = item.get('artworkUrl100', '').replace('100x100bb', '600x600bb')
                duration_ms = item.get('trackTimeMillis', 0) or 0
                mins, secs = divmod(duration_ms // 1000, 60)
                itunes_tracks.append({
                    'title': item.get('trackName', ''),
                    'artist': item.get('artistName', ''),
                    'album': item.get('collectionName', ''),
                    'image': art,
                    'duration': f"{mins}:{secs:02d}",
                    'preview_url': item.get('previewUrl', ''),
                    'itunes_url': item.get('trackViewUrl', ''),
                })
    except Exception:
        pass

    # Merge ranking songs with iTunes tracks (iTunes takes priority)
    if itunes_tracks:
        all_songs = itunes_tracks
    elif songs:
        all_songs = songs
    else:
        all_songs = []

    # Comebacks from ComebackData (current + next 2 months)
    comebacks = []
    now_cb = timezone.now()
    today_str_cb = now_cb.strftime('%Y-%m-%d')
    months_to_check = []
    y, m = now_cb.year, now_cb.month
    for _ in range(3):
        months_to_check.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    for cb_y, cb_m in months_to_check:
        cb_obj = ComebackData.objects.filter(
            year=cb_y, month=cb_m
        ).first()
        if not cb_obj:
            continue
        for date_key, day_data in cb_obj.data.items():
            for r in day_data.get('releases', []):
                artist_n = r.get('artist', '')
                title_n = r.get('title', '')
                if (
                    q.lower() in artist_n.lower()
                    or q.lower() in title_n.lower()
                ):
                    # Resolve slug for internal linking
                    cb_group = KPopGroup.objects.filter(
                        name__iexact=artist_n
                    ).first() or KPopGroup.objects.filter(
                        name__icontains=artist_n.split('(')[0].strip()
                    ).first()
                    comebacks.append({
                        'artist': artist_n,
                        'title': title_n,
                        'image': r.get('image', ''),
                        'type': r.get('type', ''),
                        'date_str': date_key,
                        'is_upcoming': date_key >= today_str_cb,
                        'slug': cb_group.slug if cb_group else '',
                    })
    # Sort: upcoming first, then most recent
    comebacks.sort(
        key=lambda x: (not x['is_upcoming'], x['date_str'])
    )
    comebacks = comebacks[:12]

    return {
        'artists': artists,
        'members': members,
        'articles': articles,
        'albums': itunes_albums,
        'songs': all_songs,
        'comebacks': comebacks,
    }


def results(request):
    q = request.GET.get('q', '').strip()
    data = _search_all(q) if q else {}
    trending_artists = []
    latest_articles = []
    if not q:
        trending_artists = list(
            KPopGroup.objects.filter(rank__isnull=False).order_by('rank')[:6]
        )
        latest_articles = list(BlogArticle.objects.order_by('-created_at')[:3])
    return render(request, 'core/results.html', {
        'q': q,
        'artists': data.get('artists', []),
        'members': data.get('members', []),
        'articles': data.get('articles', []),
        'albums': data.get('albums', []),
        'songs': data.get('songs', []),
        'comebacks': data.get('comebacks', []),
        'trending_artists': trending_artists,
        'latest_articles': latest_articles,
    })


def search_api(request):
    """JSON endpoint for live search suggestions."""
    from django.db.models import Q
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'results': []})

    results = []
    for g in KPopGroup.objects.filter(name__icontains=q)[:5]:
        results.append({
            'type': 'artist',
            'name': g.name,
            'image': g.image_url or '',
            'url': f'/idols/{g.slug}/',
            'sub': g.get_group_type_display(),
        })
    for m in KPopMember.objects.select_related('group').filter(
        Q(name__icontains=q) | Q(stage_name__icontains=q)
    )[:4]:
        results.append({
            'type': 'member',
            'name': m.stage_name or m.name,
            'image': m.image_url or '',
            'url': f'/idols/{m.group.slug}/',
            'sub': m.group.name,
        })
    for a in BlogArticle.objects.filter(
        Q(title__icontains=q) | Q(subtitle__icontains=q)
    )[:3]:
        results.append({
            'type': 'article',
            'name': a.title,
            'image': a.image or '',
            'url': f'/blog/{a.slug}/',
            'sub': a.category,
        })
    return JsonResponse({'results': results})

def bias_selector_game(request):
    import random
    import urllib.request
    import urllib.parse

    # Gather a diverse pool of artists
    artists = list(
        KPopGroup.objects.filter(
            rank__isnull=False
        ).order_by('rank')[:30]
    )
    random.shuffle(artists)

    # Enrich with an iTunes preview URL per artist
    pool = []
    for a in artists:
        preview_url = ''
        try:
            q = urllib.parse.quote(a.name)
            url = (
                f"https://itunes.apple.com/search?term={q}"
                "&entity=song&attribute=artistTerm&limit=1"
                "&genreId=51"
            )
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                results = data.get('results', [])
                if results:
                    preview_url = results[0].get(
                        'previewUrl', ''
                    )
        except Exception:
            pass

        pool.append({
            'id': a.id,
            'name': a.name,
            'slug': a.slug,
            'group_type': a.group_type,
            'group_type_display': a.get_group_type_display(),
            'label': a.label or '',
            'image_url': a.image_url or '',
            'preview_url': preview_url,
            'member_count': a.members.count(),
        })

    return render(request, 'core/bias_selector.html', {
        'pool_json': json.dumps(pool),
    })


@login_required
@require_POST
def bias_quiz_result(request):
    """Use DeepSeek to match quiz answers to an artist."""
    data = json.loads(request.body)
    answers = data.get('answers', {})
    pool_names = data.get('pool_names', [])

    prompt = (
        "You are a K-Pop bias matchmaker. "
        "Based on the following quiz answers, pick the BEST matching "
        "K-Pop artist from the provided list. You MUST pick exactly "
        "one name from the list - do not invent new names.\n\n"
        f"Available artists: {', '.join(pool_names)}\n\n"
        "Quiz answers:\n"
    )
    for key, val in answers.items():
        prompt += f"- {key}: {val}\n"
    prompt += (
        "\nRespond with ONLY a JSON object: "
        "{\"artist\": \"<exact name from list>\", "
        "\"reason\": \"<2-3 sentence explanation>\"}"
    )

    try:
        raw = _chat(
            prompt,
            system="You are a K-Pop expert matchmaker."
        )
        # Extract JSON from the response
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            result = json.loads(raw)
        # Validate the artist exists in pool
        name = result.get('artist', '')
        try:
            group = KPopGroup.objects.get(name__iexact=name)
            result['id'] = group.id
            result['artist'] = group.name
            result['slug'] = group.slug
            result['image_url'] = group.image_url or ''
            result['group_type'] = group.get_group_type_display()
            result['label'] = group.label or ''
        except KPopGroup.DoesNotExist:
            # Fallback - pick first in pool
            if pool_names:
                fb = KPopGroup.objects.filter(
                    name__in=pool_names
                ).first()
                if fb:
                    result = {
                        'artist': fb.name,
                        'id': fb.id,
                        'slug': fb.slug,
                        'image_url': fb.image_url or '',
                        'group_type': fb.get_group_type_display(),
                        'label': fb.label or '',
                        'reason': 'Matched based on your preferences.',
                    }
        return JsonResponse({'ok': True, 'result': result})
    except Exception as e:
        logger.warning("Bias quiz DeepSeek error: %s", e)
        return JsonResponse(
            {'ok': False, 'error': 'Could not determine match'},
            status=500,
        )

def _auto_rotate_station(state):
    """
    Ensures the station 'plays' in the background by fast-forwarding 
    state if songs have ended since the last update.
    """
    import random
    from datetime import timedelta
    from django.utils import timezone
    from core.models import RadioTrack
    
    if not state or not state.current_track or not state.started_at:
        return state

    now = timezone.now()
    
    # Loop to fast-forward through multiple ended songs if necessary
    for _ in range(10): # Safety break
        current_track = state.current_track
        if not current_track:
            break
            
        duration = current_track.duration_seconds or 180
        end_time = state.started_at + timedelta(seconds=duration)
        
        if now < end_time:
            # We are still in the middle of this song
            break
            
        # Song has theoretically finished. Move to history.
        history = list(state.recently_played)
        if current_track.id not in history:
            history.insert(0, current_track.id)
        state.recently_played = history[:10]
        
        # Advance to next song in queue
        queue = list(state.up_next)
        if queue:
            next_id = queue.pop(0)
            state.current_track_id = next_id
            state.up_next = queue
            state.started_at = end_time  # Next song starts at exact end of previous
        else:
            # Queue empty, refill and stop fast-forwarding for now
            all_tracks = _get_non_vo_live_track_ids()
            if all_tracks:
                state.current_track_id = random.choice(all_tracks)
                state.started_at = end_time
            break

        # Emergency refill if queue low
        if len(state.up_next) < 3:
            all_tracks = _get_non_vo_live_track_ids()
            exclude_ids = set([state.current_track_id] + list(state.recently_played) + list(state.up_next))
            pool = [tid for tid in all_tracks if tid not in exclude_ids]
            if not pool: pool = [tid for tid in all_tracks if tid not in set(state.up_next)]
            if pool:
                random.shuffle(pool)
                state.up_next = (list(state.up_next) + pool[:5])[:5]

    state.save()
    return state


def _day_code_for_datetime(dt):
    day_codes = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    return day_codes[dt.weekday()]


def _seconds_since_midnight(dt):
    return (dt.hour * 3600) + (dt.minute * 60) + dt.second


def _is_generated_voice_track(track):
    if not track:
        return False
    title = str(getattr(track, 'title', '') or '').strip()
    audio_url = str(getattr(track, 'audio_url', '') or '').lower()
    if title.startswith('VO:'):
        return True
    return '/radio/voiceovers/' in audio_url


def _get_non_vo_live_track_ids():
    return list(
        RadioTrack.objects
        .exclude(audio_url='')
        .exclude(audio_url__isnull=True)
        .exclude(title__startswith='VO:')
        .exclude(audio_url__icontains='/radio/voiceovers/')
        .values_list('id', flat=True)
    )


def _safe_track_duration_seconds(track):
    if not track:
        return 180
    try:
        seconds = int(getattr(track, 'duration_seconds', 0) or 0)
    except Exception:
        seconds = 0
    return seconds if seconds > 0 else 180


def _get_active_schedule_slot(now_local):
    day_code = _day_code_for_datetime(now_local)
    now_seconds = _seconds_since_midnight(now_local)
    slots = (
        RadioSchedule.objects
        .select_related('playlist')
        .filter(day=day_code)
        .order_by('start_time', 'id')
    )

    for slot in slots:
        start_seconds = (slot.start_time.hour * 3600) + (slot.start_time.minute * 60) + slot.start_time.second
        end_seconds = (slot.end_time.hour * 3600) + (slot.end_time.minute * 60) + slot.end_time.second
        if end_seconds <= start_seconds:
            continue
        if start_seconds <= now_seconds < end_seconds:
            return slot, start_seconds, end_seconds

    return None, None, None


def _build_live_playlist_timeline(playlist):
    timeline = []
    playlist_tracks = list(
        RadioPlaylistTrack.objects
        .select_related('track')
        .filter(playlist=playlist)
        .order_by('order', 'id')
    )
    for idx, playlist_track in enumerate(playlist_tracks):
        track = playlist_track.track
        if not track or not track.audio_url:
            continue
        if _is_generated_voice_track(track):
            continue

        duration_seconds = _safe_track_duration_seconds(track)
        voice_overlay = None

        if playlist_track.voice_over_active:
            next_playlist_track = playlist_tracks[idx + 1] if idx + 1 < len(playlist_tracks) else None
            next_track = next_playlist_track.track if next_playlist_track else None
            if next_track and next_track.audio_url and _is_generated_voice_track(next_track):
                try:
                    start_percent = int(playlist_track.voice_over_start_percent or 0)
                except Exception:
                    start_percent = 0
                start_percent = max(0, min(100, start_percent))
                start_seconds = int(round(duration_seconds * (start_percent / 100.0)))

                try:
                    duck_percent = int(playlist_track.duck_volume_percent or 10)
                except Exception:
                    duck_percent = 10
                duck_percent = max(0, min(100, duck_percent))

                voice_overlay = {
                    'audio_url': _build_stream_audio_url(next_track.audio_url),
                    'start_seconds': max(0, start_seconds),
                    'duration_seconds': _safe_track_duration_seconds(next_track),
                    'duck_volume': duck_percent / 100.0,
                }

        timeline.append({
            'track': track,
            'duration_seconds': duration_seconds,
            'voice_overlay': voice_overlay,
        })
    return timeline


def _build_schedule_context_from_index(slot, timeline, current_index, current_offset=0, started_at=None):
    if not slot or not timeline:
        return None

    timeline_len = len(timeline)
    if timeline_len <= 0:
        return None

    safe_index = max(0, min(timeline_len - 1, int(current_index or 0)))
    safe_offset = max(0, int(current_offset or 0))
    current_item = timeline[safe_index]
    current_track = current_item['track']

    up_next_tracks = []
    for step in range(1, min(6, timeline_len) + 1):
        up_next_tracks.append(timeline[(safe_index + step) % timeline_len]['track'])

    recently_played_tracks = []
    for step in range(1, min(6, timeline_len) + 1):
        recently_played_tracks.append(timeline[(safe_index - step) % timeline_len]['track'])

    resolved_started_at = started_at if started_at is not None else (timezone.now() - timedelta(seconds=safe_offset))

    return {
        'slot': slot,
        'current_track': current_track,
        'current_voice_overlay': current_item.get('voice_overlay'),
        'up_next_tracks': up_next_tracks,
        'recently_played_tracks': recently_played_tracks,
        'current_offset': safe_offset,
        'started_at': resolved_started_at,
    }


def _compute_schedule_live_context(now_local, force_advance=False):
    slot, start_seconds, _end_seconds = _get_active_schedule_slot(now_local)
    if not slot:
        return None

    timeline = _build_live_playlist_timeline(slot.playlist)
    if not timeline:
        return None

    elapsed_in_slot = max(0, _seconds_since_midnight(now_local) - start_seconds)
    cycle_duration = sum(item['duration_seconds'] for item in timeline)
    if cycle_duration <= 0:
        return None

    cycle_position = elapsed_in_slot % cycle_duration
    running_total = 0
    current_index = 0
    current_offset = 0

    for idx, item in enumerate(timeline):
        next_total = running_total + item['duration_seconds']
        if cycle_position < next_total:
            current_index = idx
            current_offset = max(0, cycle_position - running_total)
            break
        running_total = next_total

    timeline_len = len(timeline)
    if force_advance and timeline_len > 1:
        current_index = (current_index + 1) % timeline_len
        current_offset = 0

    return _build_schedule_context_from_index(
        slot,
        timeline,
        current_index,
        current_offset=current_offset,
        started_at=(timezone.now() if force_advance else None),
    )


def _compute_schedule_live_context_next_from_state(now_local, current_track_id):
    slot, _start_seconds, _end_seconds = _get_active_schedule_slot(now_local)
    if not slot:
        return None

    timeline = _build_live_playlist_timeline(slot.playlist)
    if not timeline:
        return None

    if not current_track_id:
        return _build_schedule_context_from_index(slot, timeline, 0, current_offset=0, started_at=timezone.now())

    current_index = None
    for idx, item in enumerate(timeline):
        track = item.get('track')
        if track and track.id == current_track_id:
            current_index = idx
            break

    if current_index is None:
        return None

    next_index = (current_index + 1) % len(timeline)
    return _build_schedule_context_from_index(slot, timeline, next_index, current_offset=0, started_at=timezone.now())


def _sync_state_with_schedule_context(state, context):
    if not state or not context:
        return state

    current_track = context['current_track']
    up_next_tracks = context['up_next_tracks']
    recently_played_tracks = context['recently_played_tracks']

    state.current_track_id = current_track.id if current_track else None
    state.up_next = [track.id for track in up_next_tracks if track]
    state.recently_played = [track.id for track in recently_played_tracks if track]
    state.started_at = context['started_at']
    state.save()
    return state


def _extract_primary_artist_name(raw_artist):
    text = str(raw_artist or '').strip()
    if not text:
        return ''
    lowered = text.lower()
    separators = [' feat.', ' featuring ', ' ft.', ' with ', '&', ',', '/', ' x ']
    cut_idx = len(text)
    for sep in separators:
        idx = lowered.find(sep)
        if idx != -1:
            cut_idx = min(cut_idx, idx)
    primary = text[:cut_idx].strip(' ---|')
    return re.sub(r'\s{2,}', ' ', primary).strip()


def _find_group_for_artist_name(artist_name):
    if not artist_name:
        return None
    exact = KPopGroup.objects.filter(name__iexact=artist_name).first()
    if exact:
        return exact
    starts = KPopGroup.objects.filter(name__istartswith=artist_name).order_by('rank', 'name').first()
    if starts:
        return starts
    return KPopGroup.objects.filter(name__icontains=artist_name).order_by('rank', 'name').first()


def _shorten_text(value, max_len=210):
    text = _normalize_social_text(value)
    if not text:
        return ''
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip('.,;:! ') + '...'


def _normalize_social_text(value):
    """Normalize common mojibake and whitespace for social copy."""
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not text:
        return ''

    replacements = {
        'â€¦': '...',
        '…': '...',
        'â€™': "'",
        '’': "'",
        'â€˜': "'",
        '‘': "'",
        'â€œ': '"',
        '“': '"',
        'â€�': '"',
        '”': '"',
        'â€“': '-',
        '–': '-',
        'â€”': '-',
        '—': '-',
        'Â': '',
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return re.sub(r'\s+', ' ', text).strip()


def _lyrics_snippet_api_config():
    api_url = (
        getattr(settings, 'LYRICS_SNIPPET_API_URL', '')
        or os.getenv('LYRICS_SNIPPET_API_URL', '')
    ).strip()
    api_key = (
        getattr(settings, 'LYRICS_SNIPPET_API_KEY', '')
        or os.getenv('LYRICS_SNIPPET_API_KEY', '')
    ).strip()
    return api_url, api_key


def _fetch_licensed_lyric_snippet(track):
    api_url, api_key = _lyrics_snippet_api_config()
    if not api_url or not track:
        return None

    params = {
        'artist': str(getattr(track, 'artist', '') or '').strip(),
        'title': str(getattr(track, 'title', '') or '').strip(),
    }
    headers = {'Accept': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=8)
        if response.status_code != 200:
            return None
        data = response.json() if response.content else {}
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    is_licensed = bool(data.get('is_licensed'))
    if not is_licensed:
        return None

    snippet = _shorten_text(data.get('snippet') or '', 180)
    source = _shorten_text(data.get('source') or 'Licensed lyrics', 80)
    if not snippet:
        return None

    return {
        'snippet': snippet,
        'source': source,
        'is_licensed': True,
    }


def _apply_licensed_lyric_snippet(payload, track):
    normalized = _normalize_live_ai_payload(payload, track)
    rich = normalized.get('rich_context') if isinstance(normalized.get('rich_context'), dict) else {}
    lyric = rich.get('lyric') if isinstance(rich.get('lyric'), dict) else {}
    if bool(lyric.get('is_licensed')) and str(lyric.get('body') or '').strip():
        return normalized

    snippet = _fetch_licensed_lyric_snippet(track)
    if not snippet:
        return normalized

    rich['lyric'] = {
        'title': 'Lyric Snippet',
        'body': f'"{snippet["snippet"]}"',
        'source': snippet['source'],
        'is_licensed': True,
    }
    normalized['rich_context'] = rich
    return normalized


def _comeback_context_text(group_name):
    if not group_name:
        return 'No official comeback bulletin is pinned right now, but rotation data still shows strong fan momentum and repeat-listen heat.'

    latest_records = ComebackData.objects.order_by('-year', '-month')[:4]
    lookup = str(group_name).strip().lower()
    for record in latest_records:
        data_blob = json.dumps(record.data or {}, ensure_ascii=False).lower()
        if lookup and lookup in data_blob:
            month_year = f"{record.month:02d}/{record.year}"
            return f'{group_name} appears in the latest comeback calendar ({month_year}), carrying clear era momentum and active fandom conversation.'

    return f'{group_name} stays in heavy rotation while the next confirmed comeback window is watched closely by fans.'


def _default_live_rich_context(track):
    title = str(getattr(track, 'title', '') or 'Current Track').strip()
    artist_raw = str(getattr(track, 'artist', '') or 'K-Beats').strip()
    artist_name = _extract_primary_artist_name(artist_raw) or artist_raw
    group = _find_group_for_artist_name(artist_name)

    lyric_body = (
        f'This section of {title} hits with sharp hook writing and controlled vocal phrasing, '
        f'delivering immediate crowd lift while keeping the topline clean, memorable, and built for replay.'
    )

    comeback_body = _comeback_context_text(group.name if group else artist_name)

    if group:
        member_count = KPopMember.objects.filter(group=group).count()
        group_type_label = group.get_group_type_display() if hasattr(group, 'get_group_type_display') else str(group.group_type or 'Group')
        profile_body = _shorten_text(group.description or f'{group.name} stand out for concept precision, stage chemistry, and strong replay pull across live rotation.')
        chips = [
            group_type_label,
            f'{member_count} members' if member_count else 'Line-up active',
            str(group.label or 'Agency n/a').strip(),
        ]
        profile_title = group.name
    else:
        profile_title = artist_name or artist_raw
        profile_body = f'{profile_title} translates cleanly on-air with sticky hooks, polished dynamics, and consistent replay value.'
        chips = ['Artist Focus', 'Stage Energy', 'Fan Momentum']

    return {
        'lyric': {
            'title': 'Lyric Highlight',
            'body': _shorten_text(lyric_body, 240),
            'source': '',
            'is_licensed': False,
        },
        'comeback': {
            'title': 'Era Pulse',
            'body': _shorten_text(comeback_body, 240),
        },
        'artist_profile': {
            'title': _shorten_text(profile_title, 60),
            'body': _shorten_text(profile_body, 240),
            'chips': [chip for chip in chips if str(chip or '').strip()][:3],
        },
    }


def _normalize_live_rich_context(payload, track):
    fallback = _default_live_rich_context(track)
    if not isinstance(payload, dict):
        return fallback

    def _section(name):
        raw = payload.get(name) if isinstance(payload.get(name), dict) else {}
        fallback_section = fallback[name]
        section = {
            'title': _shorten_text(raw.get('title') or fallback_section['title'], 80),
            'body': _shorten_text(raw.get('body') or fallback_section['body'], 260),
        }
        if name == 'lyric':
            section['source'] = _shorten_text(raw.get('source') or fallback_section.get('source') or '', 80)
            section['is_licensed'] = bool(raw.get('is_licensed'))
        return section

    artist_raw = payload.get('artist_profile') if isinstance(payload.get('artist_profile'), dict) else {}
    fallback_artist = fallback['artist_profile']
    raw_chips = artist_raw.get('chips') if isinstance(artist_raw.get('chips'), list) else fallback_artist['chips']
    chips = [
        _shorten_text(chip, 40)
        for chip in raw_chips
        if str(chip or '').strip()
    ][:3]
    if not chips:
        chips = fallback_artist['chips']

    return {
        'lyric': _section('lyric'),
        'comeback': _section('comeback'),
        'artist_profile': {
            'title': _shorten_text(artist_raw.get('title') or fallback_artist['title'], 80),
            'body': _shorten_text(artist_raw.get('body') or fallback_artist['body'], 260),
            'chips': chips,
        },
    }


def _default_live_ai_payload(track):
    title = (track.title if track else 'Current Track')
    artist = (track.artist if track else 'K-Beats')
    return {
        'version': 3,
        'about_label': f'About "{title}"',
        'commentary': (
            f'Now spinning {title} by {artist} on K-Beats Live. This record stands out for its performance-ready structure, '
            'strong melodic identity, and polished production choices that translate extremely well in a live radio mix. '
            'Its pacing and sonic layering keep momentum high from intro to chorus, making it a dependable anchor track in rotation.\n\n'
            f'From an audience perspective, {title} works because it balances immediate hooks with replay value. '
            'The vocal delivery and arrangement details create emotional lift while still leaving room for personality, '
            'which is exactly what keeps listeners engaged across repeat spins and cross-show transitions.'
        ),
        'cards': [
            {
                'label': 'Track Focus',
                'value': 'Now Live',
                'subtext': f'{artist}',
            },
            {
                'label': 'Energy Profile',
                'value': 'High',
                'subtext': 'K-Beats AI Estimate',
            },
            {
                'label': 'On-Air Context',
                'value': 'Featured',
                'subtext': 'Current Rotation',
            },
        ],
        'rich_context': _default_live_rich_context(track),
    }


def _normalize_live_ai_payload(payload, track):
    fallback = _default_live_ai_payload(track)
    if not isinstance(payload, dict):
        return fallback

    commentary = str(payload.get('commentary') or '').strip() or fallback['commentary']
    about_label = str(payload.get('about_label') or '').strip() or fallback['about_label']
    raw_cards = payload.get('cards') if isinstance(payload.get('cards'), list) else []

    cards = []
    for idx, card in enumerate(raw_cards[:3]):
        if not isinstance(card, dict):
            continue
        fallback_card = fallback['cards'][idx]
        cards.append({
            'label': str(card.get('label') or '').strip() or fallback_card['label'],
            'value': str(card.get('value') or '').strip() or fallback_card['value'],
            'subtext': str(card.get('subtext') or '').strip() or fallback_card['subtext'],
        })

    while len(cards) < 3:
        cards.append(fallback['cards'][len(cards)])

    rich_context = _normalize_live_rich_context(payload.get('rich_context'), track)

    return {
        'version': int(payload.get('version') or 1),
        'about_label': about_label,
        'commentary': commentary,
        'helpful_count': max(0, int(payload.get('helpful_count') or 0)),
        'cards': cards,
        'rich_context': rich_context,
    }


def _generate_live_ai_payload(track):
    fallback = _default_live_ai_payload(track)
    if not track:
        return fallback

    prompt = (
        f"You are a K-Pop music analyst for a live radio station. "
        f"For the song '{track.title}' by {track.artist}, generate concise on-air metadata. "
        f"Tone requirements: premium hype-editorial blend; energetic but credible; no slang; no clickbait; avoid exaggerated claims. "
        f"Use UK English spelling and phrasing throughout. "
        f"Return ONLY valid JSON in this exact shape: "
        '{"version":3,"about_label":"About \\\"<song>\\\"","commentary":"minimum 2 paragraphs; each paragraph 2-4 sentences",'
        '"cards":[{"label":"...","value":"...","subtext":"..."},'
        '{"label":"...","value":"...","subtext":"..."},'
        '{"label":"...","value":"...","subtext":"..."}],'
        '"rich_context":{'
        '"lyric":{"title":"Lyric Highlight","body":"1-2 sentences on songwriting/vocal/performance feel"},'
        '"comeback":{"title":"Era Pulse","body":"1-2 sentences on era/comeback momentum using cautious wording"},'
        '"artist_profile":{"title":"<artist or group>","body":"1-2 sentences mini-profile","chips":["Artist Focus","Stage Energy","Fan Momentum"]}'
        '}}'
    )

    try:
        raw = _chat(
            prompt,
            system=(
                'You are an expert K-Pop radio metadata writer. '
                'Write in a premium hype-editorial style: vivid, concise, and grounded. '
                'Prioritise musical observations, era context, and fan-facing relevance without speculation.'
            ),
        )
        start = raw.find('{')
        end = raw.rfind('}') + 1
        if start == -1 or end <= start:
            return _apply_licensed_lyric_snippet(fallback, track)
        parsed = json.loads(raw[start:end])
        return _apply_licensed_lyric_snippet(parsed, track)
    except Exception:
        return _apply_licensed_lyric_snippet(fallback, track)


def _get_or_generate_live_ai_payload(track):
    if not track:
        return _default_live_ai_payload(None)

    normalized_existing = _normalize_live_ai_payload(track.live_ai_payload or {}, track)
    existing_commentary = str((track.live_ai_payload or {}).get('commentary') or '').strip()
    existing_paragraphs = [p for p in re.split(r'\n\s*\n', existing_commentary) if p.strip()]
    has_existing = bool(existing_commentary)
    is_fresh_format = (
        int((track.live_ai_payload or {}).get('version') or 1) >= 3
        and len(existing_paragraphs) >= 2
    )
    if has_existing and is_fresh_format:
        enriched_existing = _apply_licensed_lyric_snippet(normalized_existing, track)
        if enriched_existing != normalized_existing:
            try:
                track.live_ai_payload = enriched_existing
                track.live_ai_generated_at = timezone.now()
                track.save(update_fields=['live_ai_payload', 'live_ai_generated_at'])
            except Exception:
                pass
        return enriched_existing

    generated = _generate_live_ai_payload(track)
    try:
        track.live_ai_payload = generated
        track.live_ai_generated_at = timezone.now()
        track.save(update_fields=['live_ai_payload', 'live_ai_generated_at'])
    except Exception:
        pass
    return generated


LIVE_DAY_SEQUENCE = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']


def _day_label_for_code(day_code):
    return dict(RadioSchedule.DAY_CHOICES).get(str(day_code or '').upper(), str(day_code or '').upper())


def _combine_local_date_and_time(target_date, target_time):
    naive = datetime.combine(target_date, target_time)
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _relative_day_label(target_date, current_date):
    if target_date == current_date:
        return 'Today'
    if target_date == current_date + timedelta(days=1):
        return 'Tomorrow'
    return target_date.strftime('%A')


def _build_live_show_snapshot(now_local):
    schedules = list(
        RadioSchedule.objects
        .select_related('playlist')
        .order_by('day', 'start_time', 'id')
    )
    if not schedules:
        return {'current': None, 'next': None}

    playlist_by_id = {slot.playlist.id: slot.playlist for slot in schedules}
    playlist_preview_by_id = _build_playlist_preview_by_id(playlist_by_id)
    assigned_host_by_playlist, assigned_host_by_day, global_assigned_host = _build_assigned_host_maps()
    schedules_by_day = {day: [] for day in LIVE_DAY_SEQUENCE}
    for slot in schedules:
        schedules_by_day.setdefault(slot.day, []).append(slot)

    def serialize_slot(slot, target_date, start_at, end_at, *, is_live=False):
        common = _serialize_schedule_slot_common(
            slot,
            playlist_preview_by_id,
            assigned_host_by_playlist,
            assigned_host_by_day,
            global_assigned_host,
        )
        countdown_target = end_at if is_live else start_at
        countdown_seconds = max(0, int((countdown_target - now_local).total_seconds()))
        show_name = common['show_name'] or common['playlist_name']
        description = _shorten_text(
            common['playlist_preview']
            or common['show_name']
            or slot.description
            or slot.playlist.description,
            180,
        )
        return {
            'show_name': show_name,
            'playlist_name': common['playlist_name'],
            'host_name': common['host_name'],
            'genre': common['genre'],
            'description': description,
            'day_code': slot.day,
            'day_label': _day_label_for_code(slot.day),
            'relative_day_label': _relative_day_label(target_date, now_local.date()),
            'date_label': target_date.strftime('%a %d %b'),
            'time_label': start_at.strftime('%H:%M'),
            'time_range_label': f'{start_at:%H:%M} - {end_at:%H:%M}',
            'countdown_seconds': countdown_seconds,
            'countdown_prefix': 'Ends in' if is_live else 'Starts in',
            'starts_at_iso': start_at.isoformat(),
            'ends_at_iso': end_at.isoformat(),
            'is_live': bool(is_live),
        }

    current_slot, _start_seconds, _end_seconds = _get_active_schedule_slot(now_local)
    current_payload = None
    if current_slot:
        current_date = now_local.date()
        current_start = _combine_local_date_and_time(current_date, current_slot.start_time)
        current_end = _combine_local_date_and_time(current_date, current_slot.end_time)
        if current_end <= current_start:
            current_end += timedelta(days=1)
        current_payload = serialize_slot(
            current_slot,
            current_date,
            current_start,
            current_end,
            is_live=True,
        )

    next_payload = None
    base_date = now_local.date()
    for day_offset in range(0, 8):
        target_date = base_date + timedelta(days=day_offset)
        target_day = LIVE_DAY_SEQUENCE[target_date.weekday()]
        for slot in schedules_by_day.get(target_day, []):
            start_at = _combine_local_date_and_time(target_date, slot.start_time)
            if start_at <= now_local:
                continue
            end_at = _combine_local_date_and_time(target_date, slot.end_time)
            if end_at <= start_at:
                end_at += timedelta(days=1)
            next_payload = serialize_slot(slot, target_date, start_at, end_at, is_live=False)
            break
        if next_payload:
            break

    return {
        'current': current_payload,
        'next': next_payload,
    }


def _build_live_request_momentum(current_track, up_next_tracks, requested_titles):
    def _normalize_title(value):
        return str(value or '').strip().lower()

    def _relative_request_time(created_at):
        if not created_at:
            return 'Just now'
        delta_seconds = max(0, int((timezone.now() - created_at).total_seconds()))
        if delta_seconds < 60:
            return 'Just now'
        if delta_seconds < 3600:
            minutes = max(1, delta_seconds // 60)
            return f'{minutes} min ago' if minutes == 1 else f'{minutes} mins ago'
        if delta_seconds < 86400:
            hours = max(1, delta_seconds // 3600)
            return f'{hours} hr ago' if hours == 1 else f'{hours} hrs ago'
        days = max(1, delta_seconds // 86400)
        return f'{days} day ago' if days == 1 else f'{days} days ago'

    requested_lookup = {
        _normalize_title(title)
        for title in (requested_titles or [])
        if _normalize_title(title)
    }
    recent_request_qs = SongRequest.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-created_at')
    requests_last_24h = recent_request_qs.count()
    recent_requests = list(recent_request_qs[:5])
    queued_requested_count = sum(
        1
        for track in (up_next_tracks or [])
        if _normalize_title(getattr(track, 'title', '')) in requested_lookup
    )
    current_track_requested = bool(
        current_track
        and _normalize_title(getattr(current_track, 'title', '')) in requested_lookup
    )
    request_lookup = {}
    latest_requests_payload = []
    for req in recent_requests:
        normalized_song = _normalize_title(req.song_title)
        request_payload = {
            'song_title': req.song_title,
            'artist': req.artist,
            'listener_name': req.listener_name or 'Listener',
            'time_ago': _relative_request_time(req.created_at),
        }
        latest_requests_payload.append(request_payload)
        if normalized_song and normalized_song not in request_lookup:
            request_lookup[normalized_song] = {
                'listener_name': request_payload['listener_name'],
                'time_ago': request_payload['time_ago'],
            }
    return {
        'requests_last_24h': requests_last_24h,
        'queued_requested_count': queued_requested_count,
        'current_track_requested': current_track_requested,
        'has_activity': bool(requests_last_24h or queued_requested_count or current_track_requested),
        'latest_requests': latest_requests_payload,
        'request_lookup': request_lookup,
    }


def _build_live_poll_context(request):
    display_question = "Who's your artist of the week?"
    display_heading = "Artist Of The Week"
    display_intro = (
        "Cast your vote for this week's takeover. The winner gets a dedicated K-Beats "
        "station playing nothing but their biggest hits all week, so don't miss your chance to decide it."
    )
    display_status_prompt = (
        "Cast your vote now to decide which artist gets the next full-week takeover station."
    )
    display_status_voted = "Vote locked in. You just pushed this week's takeover race."
    display_leader_label = "Takeover Leader"
    display_option_labels = [
        "BTS",
        "BLACKPINK",
        "ATEEZ",
        "BABYMONSTER",
        "STRAY KIDS",
    ]
    display_results_version = "bts-38-blackpink-24-v1"

    def _seeded_int(seed_key, minimum, maximum):
        lower = int(minimum)
        upper = int(maximum)
        if upper <= lower:
            return lower
        digest = hashlib.sha256(seed_key.encode('utf-8')).hexdigest()
        return lower + (int(digest[:8], 16) % ((upper - lower) + 1))

    def _build_display_vote_profile(option_labels):
        now_local = timezone.localtime(timezone.now(), ZoneInfo('Europe/London'))
        day_key = now_local.strftime('%Y-%m-%d')
        base_total = 1578
        incremental_total = sum(
            _seeded_int(f'live-poll-hourly:{day_key}:{hour}', 9, 22)
            for hour in range(int(now_local.hour) + 1)
        )
        total = min(2162, base_total + incremental_total)
        target_percentages = [38, 24, 16, 12, 10]
        votes = [max(1, round((percentage / 100) * total)) for percentage in target_percentages[:len(option_labels)]]
        if votes:
            votes[0] += total - sum(votes)

        options = []
        for idx, label in enumerate(option_labels):
            count = max(1, votes[idx])
            options.append({
                'text': label,
                'votes': count,
                'percentage': target_percentages[idx] if idx < len(target_percentages) else round((count / total) * 100),
            })

        return {
            'total_votes': total,
            'options': options,
            'hourly_growth_min': 9,
            'hourly_growth_max': 22,
            'winning_option_text': option_labels[0] if option_labels else '',
            'target_percentages': target_percentages[:len(option_labels)],
        }

    poll = (
        LivePoll.objects
        .select_related('early_access_group')
        .prefetch_related('options')
        .filter(is_active=True)
        .order_by('-created_at')
        .first()
    )
    if not poll:
        return None

    locked = _is_poll_early_access_locked(request, poll)
    display_vote_profile = _build_display_vote_profile(display_option_labels)
    total_votes = int(display_vote_profile['total_votes'])
    early_access_note = ''
    if poll.early_access_starts_at and poll.early_access_group:
        unlocks_at = timezone.localtime(poll.early_access_starts_at)
        early_access_note = (
            f'{poll.early_access_group.name} {poll.early_access_min_tier} members can vote early '
            f'until {unlocks_at:%a %H:%M}.'
        )

    poll_options = list(poll.options.all())[:len(display_option_labels)]
    options_payload = []
    for idx, option in enumerate(poll_options):
        display_text = display_option_labels[idx] if idx < len(display_option_labels) else option.text
        display_option = display_vote_profile['options'][idx] if idx < len(display_vote_profile['options']) else None
        options_payload.append({
            'id': option.id,
            'text': display_text,
            'votes': int(display_option['votes']) if display_option else option.votes,
            'percentage': int(display_option['percentage']) if display_option else option.percentage(),
        })

    leading_option = None
    if options_payload and total_votes > 0:
        leading_option = max(options_payload, key=lambda item: (item['votes'], item['percentage']))

    return {
        'id': poll.id,
        'heading': display_heading,
        'intro': display_intro,
        'question': display_question,
        'locked': locked,
        'locked_message': (
            'Early access is reserved for eligible fan-club members right now.'
            if locked else ''
        ),
        'leader_label': display_leader_label,
        'status_prompt': display_status_prompt,
        'status_voted': display_status_voted,
        'early_access_note': early_access_note,
        'total_votes': total_votes,
        'leading_option': leading_option,
        'options': options_payload,
        'simulated_results': True,
        'hourly_growth_min': display_vote_profile['hourly_growth_min'],
        'hourly_growth_max': display_vote_profile['hourly_growth_max'],
        'winning_option_text': display_vote_profile['winning_option_text'],
        'simulated_results_version': display_results_version,
        'target_percentages': display_vote_profile['target_percentages'],
    }


def _build_live_room_hype(live_request_momentum, live_poll):
    requests_last_24h = int((live_request_momentum or {}).get('requests_last_24h') or 0)
    queued_requested_count = int((live_request_momentum or {}).get('queued_requested_count') or 0)
    current_track_requested = bool((live_request_momentum or {}).get('current_track_requested'))
    latest_requests_count = len((live_request_momentum or {}).get('latest_requests') or [])
    total_votes = int((live_poll or {}).get('total_votes') or 0)

    score = min(
        100,
        (requests_last_24h * 10)
        + (queued_requested_count * 18)
        + (total_votes * 4)
        + (latest_requests_count * 8)
        + (12 if current_track_requested else 0),
    )

    if score >= 75:
        return {
            'label': 'On Fire',
            'percent': score,
            'summary': 'Requests, votes, and queue movement are all lighting up the room right now.',
        }
    if score >= 45:
        return {
            'label': 'Buzzing',
            'percent': score,
            'summary': 'The room has momentum and fan choices are starting to shape what lands next.',
        }
    if score >= 15:
        return {
            'label': 'Building',
            'percent': score,
            'summary': 'A few early votes and requests are warming the room up for the next handoff.',
        }
    return {
        'label': 'Warm Up',
        'percent': max(score, 8),
        'summary': 'The room is ready for its first push. One request or vote can set tonight’s energy.',
    }


def _build_live_return_profile(user, profile, current_track):
    base = {
        'is_authenticated': False,
        'tier': 'FREE',
        'saved_moments_count': 0,
        'current_track_saved': False,
        'saved_moments': [],
        'current_streak': 0,
        'longest_streak': 0,
        'weekly_stream_total': 0,
        'today_stream_total': 0,
        'digest_enabled': False,
        'digest_summary': 'Log in to save live moments, build a streak, and unlock reminder nudges.',
        'streak_message': 'Log in so every live session can build toward a return streak.',
    }
    if not user or not user.is_authenticated:
        return base

    saved_qs = FavouriteSong.objects.filter(user=user).order_by('-added_at')
    saved_moments = list(saved_qs[:3])
    saved_moments_count = saved_qs.count()
    activity_days = _activity_day_set_for_user(user)
    today = timezone.localdate()
    streaks = _calculate_activity_streaks(activity_days, today)
    week_cutoff = timezone.now() - timedelta(days=7)
    weekly_stream_total = RadioTrackPlay.objects.filter(
        user=user,
        listened_at__gte=week_cutoff,
    ).count()
    today_stream_total = RadioTrackPlay.objects.filter(
        user=user,
        listened_at__date=today,
    ).count()
    tier = _user_highest_tier(user)
    digest_timezone = (profile.digest_timezone if profile else 'Europe/London') or 'Europe/London'
    digest_hour = int(profile.digest_hour if profile else 8)
    digest_enabled = bool(profile.digest_enabled) if profile else False
    if digest_enabled:
        digest_summary = f'Daily digest set for {digest_hour:02d}:00 {digest_timezone}.'
    else:
        digest_summary = 'Reminder digest is off. Turn it on in personalisation settings.'

    if streaks['current'] >= 7:
        streak_message = 'Seven-day momentum is live. Drop back in tomorrow to keep the run going.'
    elif streaks['current'] >= 3:
        streak_message = 'Your Daily Pulse streak is active. Tomorrow keeps the streak alive.'
    elif streaks['current'] >= 1:
        streak_message = 'Momentum is building. Come back tomorrow to extend your listening streak.'
    else:
        streak_message = 'Start a fresh streak by dropping back in tomorrow or saving tonight\'s set.'

    current_track_saved = False
    if current_track:
        current_track_saved = saved_qs.filter(
            title=str(getattr(current_track, 'title', '') or '').strip(),
            artist=str(getattr(current_track, 'artist', '') or '').strip(),
        ).exists()

    return {
        'is_authenticated': True,
        'tier': tier,
        'saved_moments_count': saved_moments_count,
        'current_track_saved': current_track_saved,
        'saved_moments': [
            {
                'title': item.title,
                'artist': item.artist,
            }
            for item in saved_moments
        ],
        'current_streak': streaks['current'],
        'longest_streak': streaks['longest'],
        'weekly_stream_total': weekly_stream_total,
        'today_stream_total': today_stream_total,
        'digest_enabled': digest_enabled,
        'digest_summary': digest_summary,
        'streak_message': streak_message,
    }

def _build_live_page_context(request):
    from datetime import timedelta

    profile = None
    station_group_names = []
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        onboarding_redirect = _maybe_redirect_to_onboarding(request, profile)
        if onboarding_redirect:
            return onboarding_redirect
        station_group_names = _station_group_names_from_profile(profile)

    cutoff = timezone.now() - timedelta(hours=24)
    requested = SongRequest.objects.filter(
        created_at__gte=cutoff
    ).values_list('song_title', flat=True)
    requested_titles = [t.lower() for t in requested]

    # Fetch Radio Station State and use scheduler-linked playback when possible
    state, _ = RadioStationState.objects.get_or_create(id=1)
    schedule_context = _compute_schedule_live_context(timezone.localtime())
    if schedule_context:
        state = _sync_state_with_schedule_context(state, schedule_context)
    else:
        state = _auto_rotate_station(state)

    current_track = None
    current_voice_overlay = None
    up_next_tracks = []
    recently_played_tracks = []

    if schedule_context:
        current_track = schedule_context['current_track']
        current_voice_overlay = schedule_context.get('current_voice_overlay')
        if current_track:
            current_track.audio_url = _build_stream_audio_url(current_track.audio_url)
        if current_voice_overlay and current_voice_overlay.get('audio_url'):
            current_voice_overlay['audio_url'] = _build_stream_audio_url(current_voice_overlay.get('audio_url'))
        up_next_tracks = schedule_context['up_next_tracks'][:6]
        recently_played_tracks = schedule_context['recently_played_tracks'][:6]
    elif state:
        current_track = state.current_track
        if _is_generated_voice_track(current_track):
            current_track = None
        elif current_track:
            current_track.audio_url = _build_stream_audio_url(current_track.audio_url)

        # Fetch up_next tracks in order, limit to 6
        up_next_ids = (state.up_next or [])[:6]
        up_next_tracks = list(RadioTrack.objects.filter(id__in=up_next_ids))
        up_next_tracks = [track for track in up_next_tracks if not _is_generated_voice_track(track)]
        # Preserving order from list
        up_next_tracks.sort(key=lambda t: up_next_ids.index(t.id) if t.id in up_next_ids else 999)

        # Fetch recently_played tracks in order, limit to 6
        recent_ids = (state.recently_played or [])[:6]
        recently_played_tracks = list(RadioTrack.objects.filter(id__in=recent_ids))
        recently_played_tracks = [track for track in recently_played_tracks if not _is_generated_voice_track(track)]
        recently_played_tracks.sort(key=lambda t: recent_ids.index(t.id) if t.id in recent_ids else 999)

    if station_group_names:
        up_next_tracks = _sort_items_for_station(
            up_next_tracks,
            lambda track: _text_matches_station([getattr(track, 'artist', ''), getattr(track, 'title', '')], station_group_names),
        )
        recently_played_tracks = _sort_items_for_station(
            recently_played_tracks,
            lambda track: _text_matches_station([getattr(track, 'artist', ''), getattr(track, 'title', '')], station_group_names),
        )

    _record_live_track_play(request, current_track)

    live_ai_payload = _get_or_generate_live_ai_payload(current_track)
    live_show_snapshot = _build_live_show_snapshot(timezone.localtime())
    live_request_momentum = _build_live_request_momentum(
        current_track,
        up_next_tracks,
        requested_titles,
    )
    live_poll = _build_live_poll_context(request)
    live_room_hype = _build_live_room_hype(live_request_momentum, live_poll)
    live_return_profile = _build_live_return_profile(request.user, profile, current_track)

    # Calculate offset for synchronization
    current_offset = 0
    if schedule_context:
        current_offset = schedule_context['current_offset']
    elif state and state.started_at:
        elapsed = timezone.now() - state.started_at
        current_offset = max(0, int(elapsed.total_seconds()))

    current_track_payload = None
    if current_track:
        current_track_payload = {
            'id': current_track.id,
            'title': current_track.title,
            'artist': current_track.artist,
            'album_art': current_track.album_art,
            'audio_url': current_track.audio_url,
            'duration_seconds': int(current_track.duration_seconds or 0),
        }

    return {
        'requested_titles': requested_titles,
        'requested_titles_json': json.dumps(requested_titles),
        'state': state,
        'current_track': current_track,
        'current_track_saved': live_return_profile['current_track_saved'],
        'current_track_json': json.dumps(current_track_payload),
        'current_track_id': (current_track.id if current_track else None),
        'current_track_duration_seconds': (current_track.duration_seconds if current_track else 0),
        'current_voice_overlay_json': json.dumps(current_voice_overlay),
        'up_next_tracks': up_next_tracks,
        'recently_played_tracks': recently_played_tracks,
        'live_show_snapshot': live_show_snapshot,
        'live_request_momentum': live_request_momentum,
        'requested_track_lookup_json': json.dumps(live_request_momentum.get('request_lookup', {})),
        'live_poll': live_poll,
        'live_poll_json': json.dumps(live_poll),
        'live_room_hype': live_room_hype,
        'live_return_profile': live_return_profile,
        'up_next_tracks_json': json.dumps([
            {
                'title': t.title,
                'artist': t.artist,
                'album_art': t.album_art,
                'duration_seconds': int(t.duration_seconds or 0),
            }
            for t in up_next_tracks[:6]
        ]),
        'current_offset': current_offset,
        'live_ai_payload': live_ai_payload,
        'live_ai_payload_json': json.dumps(live_ai_payload),
    }


def _get_live_experience_suggestions():
    return [
        {
            'eyebrow': 'Now Live 01',
            'title': 'Appointment listening is built into the page',
            'summary': 'The live experience now surfaces the current show, the next handoff, and clear countdowns so fans always know when to return.',
            'impact': 'The schedule now creates concrete return times instead of feeling anonymous.',
        },
        {
            'eyebrow': 'Now Live 02',
            'title': 'The stream feels like a room, not just a player',
            'summary': 'Listener chat, fan voting, and visible room energy make the page feel inhabited before and after someone presses play.',
            'impact': 'Community signals strengthen session depth and repeat visits.',
        },
        {
            'eyebrow': 'Now Live 03',
            'title': 'Saved moments now behave like a memory archive',
            'summary': 'The save flow now connects to a visible archive layer so favourite songs and on-air highs feel collectible instead of disposable.',
            'impact': 'Collecting adds ownership and gives listeners a reason to come back to their archive.',
        },
        {
            'eyebrow': 'Now Live 04',
            'title': 'Fan influence is visible in the listening flow',
            'summary': 'Requests, poll activity, and queue momentum now make it clearer where listeners shape what happens on air.',
            'impact': 'Visible agency makes people more likely to return and participate again.',
        },
        {
            'eyebrow': 'Now Live 05',
            'title': 'Loyalty loops are now part of the page rhythm',
            'summary': 'Streak status, reminder state, and repeat-listen cues now give regulars a lightweight ritual instead of a one-off visit.',
            'impact': 'Small recurring loops help turn casual visitors into regulars.',
        },
    ]


def _resolve_live_page_context(request):
    context = _build_live_page_context(request)
    if not isinstance(context, dict):
        return context

    context['live_experience_suggestions'] = _get_live_experience_suggestions()
    return context


def _stream_presets():
    return [
        {
            'slug': 'live-now',
            'name': 'Live Now',
            'preset': 'Free Signal',
            'tagline': 'The full station feed with the same real-time energy as the main Live page.',
            'description': 'Drop into the live K-Beats rotation with the current on-air track, next-up queue, and live editorial context.',
            'mood': 'On Air',
            'tier': 'FREE',
            'accent': '244, 37, 192',
            'secondary': '0, 240, 255',
            'best_for': 'Jumping straight into the broadcast without the extra chrome of the main Live page.',
            'note': 'Built for listeners who want the full player experience in a dedicated Stream layout.',
            'genres': ['Live', 'Schedule Sync', 'Free'],
            'perks': [
                'Real-time now-playing sync with the main station.',
                'A focused player layout for listening sessions.',
                'Quick links into the queue and related presets.',
            ],
            'required_tier': 'FREE',
        },
        {
            'slug': 'chart-heat',
            'name': 'Chart Heat',
            'preset': 'Mood Preset',
            'tagline': 'A sharper, brighter take on the live player for peak-hour listening.',
            'description': 'Styled like a high-velocity stream lane with bolder chart-driven copy, hot accents, and the same live audio core.',
            'mood': 'Peak Energy',
            'tier': 'FREE',
            'accent': '255, 96, 64',
            'secondary': '255, 210, 63',
            'best_for': 'Listeners who want a louder visual treatment while the live station is in full motion.',
            'note': "Same live source, but framed like the station's momentum channel.",
            'genres': ['Charts', 'High Energy', 'Free'],
            'perks': [
                'Shares the active live radio source.',
                'Pushes chart-led visuals and hotter color treatment.',
                'Keeps queue awareness front and center.',
            ],
            'required_tier': 'FREE',
        },
        {
            'slug': 'after-midnight',
            'name': 'After Midnight',
            'preset': 'Mood Preset',
            'tagline': 'A calmer stream shell for late-night sessions and lower-stim listening.',
            'description': 'Softens the palette while keeping the same live sync underneath, giving the player a more after-hours, headphones-on feel.',
            'mood': 'After Hours',
            'tier': 'FREE',
            'accent': '96, 165, 250',
            'secondary': '56, 189, 248',
            'best_for': 'Background listening, night drives, and a more chilled player mood.',
            'note': 'Same station, tuned visually for slower sessions.',
            'genres': ['Night Shift', 'Low Glow', 'Free'],
            'perks': [
                'Keeps the live station available in a softer visual frame.',
                'Designed for long listening sessions and lower visual noise.',
                'Uses the same now-playing and queue sync as Live.',
            ],
            'required_tier': 'FREE',
        },
        {
            'slug': 'deeper-cuts',
            'name': 'Deeper Cuts',
            'preset': 'Premium Preset',
            'tagline': 'Premium framing for listeners who want the station to feel more editorial and collector-led.',
            'description': 'A premium stream skin with richer copy blocks, collector positioning, and access messaging for paid listeners.',
            'mood': 'Collector Mode',
            'tier': 'PLUS',
            'accent': '255, 255, 255',
            'secondary': '244, 37, 192',
            'best_for': 'Fans who want a more premium, editorial listening space around the live feed.',
            'note': 'Requires a Plus-tier fan-club membership or higher.',
            'genres': ['Premium', 'Editorial', 'Plus'],
            'perks': [
                'Premium visual framing with collector-style messaging.',
                'Dedicated membership gating and upsell surface.',
                'A more polished lounge feel around the same live player core.',
            ],
            'required_tier': 'PLUS',
        },
        {
            'slug': 'smooth-seoul',
            'name': 'Smooth Seoul',
            'preset': 'Premium Preset',
            'tagline': 'A luxe, lounge-coded version of the player for softer sessions.',
            'description': 'Leans into premium late-night listening with smoother gradients, cleaner spacing, and a calmer premium tone.',
            'mood': 'Lounge Glow',
            'tier': 'PLUS',
            'accent': '45, 212, 191',
            'secondary': '244, 114, 182',
            'best_for': 'Late-night listening, quieter sessions, and premium members who want a softer atmosphere.',
            'note': 'Requires a Plus-tier fan-club membership or higher.',
            'genres': ['Premium', 'Lounge', 'Plus'],
            'perks': [
                'Premium-only presentation built for calmer listening.',
                'Same synced live station with a softer visual identity.',
                'Fast path into premium membership upsell when locked.',
            ],
            'required_tier': 'PLUS',
        },
        {
            'slug': 'study-hall',
            'name': 'Study Hall',
            'preset': 'Premium Preset',
            'tagline': 'A cleaner utility-first player page for focused work sessions.',
            'description': 'Keeps the player prominent, lowers visual distraction, and frames the stream like a premium focus tool.',
            'mood': 'Focus Mode',
            'tier': 'PLUS',
            'accent': '192, 132, 252',
            'secondary': '96, 165, 250',
            'best_for': 'Long focus blocks, studying, and a more minimal premium stream shell.',
            'note': 'Requires a Plus-tier fan-club membership or higher.',
            'genres': ['Premium', 'Focus', 'Plus'],
            'perks': [
                'Reduced-noise layout for long sessions.',
                'Keeps queue and now-playing context easy to scan.',
                'Premium gate can upsell directly into plan selection.',
            ],
            'required_tier': 'PLUS',
        },
        {
            'slug': 'artist-of-the-week',
            'name': 'Artist Of The Week',
            'preset': 'Ultra Preset',
            'tagline': 'The top-tier stream shell with the most elevated editorial framing.',
            'description': 'A hero-led premium player variant built for Ultra listeners, with stronger spotlight language and collector-forward positioning.',
            'mood': 'Spotlight',
            'tier': 'ULTRA',
            'accent': '250, 204, 21',
            'secondary': '244, 114, 182',
            'best_for': 'Ultra members who want the stream presented like a flagship feature.',
            'note': 'Requires an Ultra-tier fan-club membership.',
            'genres': ['Ultra', 'Spotlight', 'Premium'],
            'perks': [
                'Top-tier premium framing for the live feed.',
                'Strongest spotlight treatment and membership positioning.',
                'Reserved for Ultra listeners.',
            ],
            'required_tier': 'ULTRA',
        },
    ]


def _get_stream_preset(slug):
    for preset in _stream_presets():
        if preset['slug'] == slug:
            return preset
    raise Http404('Stream preset not found')


def live(request):
    context = _resolve_live_page_context(request)
    if not isinstance(context, dict):
        return context
    return render(request, 'core/live_experience.html', context)


def test_page(request):
    return render(request, 'core/test_page.html', {
        'current_home_url': reverse('home'),
        'redesign_home_url': reverse('home_redesign_lab'),
        'comparison_cards': [
            {
                'eyebrow': 'Hero',
                'title': 'Broadcast signal panel',
                'summary': 'The redesign trades the comeback card stack for a cleaner signal panel with live status, the next release, and stronger listening CTAs.',
            },
            {
                'eyebrow': 'Flow',
                'title': 'Faster editorial scan',
                'summary': 'Upper-page hierarchy is tightened so the hero, live rail, programming, trending, and news each do one clear job.',
            },
            {
                'eyebrow': 'Polish',
                'title': 'Quieter front-end',
                'summary': 'The variant avoids the client-side artwork fetches and null-target particle script so review stays focused on the redesign itself.',
            },
        ],
    })


def stream_hub(request):
    context = _build_live_page_context(request)
    if not isinstance(context, dict):
        return context
    user_tier = _user_highest_tier(request.user)
    presets = []
    for preset in _stream_presets():
        stream_data = dict(preset)
        stream_data['href'] = reverse('stream_player', args=[preset['slug']])
        stream_data['locked'] = not _tier_meets_requirement(user_tier, preset['required_tier'])
        presets.append(stream_data)

    context.update({
        'stream_presets': presets,
        'stream_presets_free': [preset for preset in presets if preset['required_tier'] == 'FREE'],
        'stream_presets_premium': [preset for preset in presets if preset['required_tier'] != 'FREE'],
        'user_stream_tier': user_tier,
    })
    return render(request, 'core/stream_hub.html', context)


def stream_player(request, slug):
    context = _build_live_page_context(request)
    if not isinstance(context, dict):
        return context
    preset = dict(_get_stream_preset(slug))
    user_tier = _user_highest_tier(request.user)
    has_access = _tier_meets_requirement(user_tier, preset['required_tier'])
    preset['href'] = reverse('stream_player', args=[preset['slug']])

    related_presets = []
    for item in _stream_presets():
        item_copy = dict(item)
        item_copy['href'] = reverse('stream_player', args=[item['slug']])
        item_copy['locked'] = not _tier_meets_requirement(user_tier, item['required_tier'])
        related_presets.append(item_copy)

    context.update({
        'stream_preset': preset,
        'stream_has_access': has_access,
        'stream_required_tier': preset['required_tier'],
        'user_stream_tier': user_tier,
        'stream_related_presets': related_presets,
    })
    return render(request, 'core/stream_player.html', context)

def api_live_rotate_track(request):
    """
    Rotates the radio station to the next track in the queue.
    """
    from core.models import RadioStationState, RadioTrack
    import random

    state, _ = RadioStationState.objects.get_or_create(id=1)

    advance_requested = str(request.GET.get('advance') or '').strip().lower() in ('1', 'true', 'yes', 'on')
    if advance_requested:
        schedule_context = _compute_schedule_live_context_next_from_state(timezone.localtime(), state.current_track_id)
        if not schedule_context:
            schedule_context = _compute_schedule_live_context(timezone.localtime(), force_advance=True)
    else:
        schedule_context = _compute_schedule_live_context(timezone.localtime(), force_advance=False)
    if schedule_context:
        _sync_state_with_schedule_context(state, schedule_context)
        current = schedule_context['current_track']
        _record_live_track_play(request, current)
        live_ai_payload = _get_or_generate_live_ai_payload(current)
        current_track_saved = False
        if request.user.is_authenticated and current:
            current_track_saved = FavouriteSong.objects.filter(
                user=request.user,
                title=str(current.title or '').strip(),
                artist=str(current.artist or '').strip(),
            ).exists()
        up_next_list = schedule_context['up_next_tracks'][:6]
        recently_played_list = schedule_context['recently_played_tracks'][:6]

        return JsonResponse({
            'ok': True,
            'current_offset': schedule_context['current_offset'],
            'voice_overlay': schedule_context.get('current_voice_overlay'),
            'current_track_saved': current_track_saved,
            'current_track': {
                'id': current.id,
                'title': current.title,
                'artist': current.artist,
                'album_art': current.album_art,
                'audio_url': _build_stream_audio_url(current.audio_url),
                'duration': current.duration,
                'duration_seconds': current.duration_seconds,
            },
            'live_ai_payload': live_ai_payload,
            'up_next': [
                {
                    'title': t.title,
                    'artist': t.artist,
                    'album_art': t.album_art,
                    'duration_seconds': int(t.duration_seconds or 0),
                }
                for t in up_next_list
            ],
            'recently_played': [
                {'title': t.title, 'artist': t.artist, 'album_art': t.album_art}
                for t in recently_played_list
            ]
        })

    # Catch-up current state first
    state = _auto_rotate_station(state)

    # Move current to history
    if state.current_track_id:
        history = list(state.recently_played)
        if state.current_track_id not in history:
            history.insert(0, state.current_track_id)
        state.recently_played = history[:10]  # Keep last 10

    # Rotate song
    queue = list(state.up_next)
    if queue:
        next_id = queue.pop(0)
        state.current_track_id = next_id
        state.up_next = queue
    else:
        # Emergency refill if queue is empty
        all_tracks = _get_non_vo_live_track_ids()
        if all_tracks:
            state.current_track_id = random.choice(all_tracks)

    # Refill queue if low
    if len(state.up_next) < 3:
        all_tracks = _get_non_vo_live_track_ids()
        exclude_ids = set([state.current_track_id] + list(state.recently_played) + list(state.up_next))
        pool = [tid for tid in all_tracks if tid not in exclude_ids]
        
        # If pool is empty, just use any tracks not in up_next
        if not pool:
            pool = [tid for tid in all_tracks if tid not in set(state.up_next)]
            
        if pool:
            random.shuffle(pool)
            new_queue = list(state.up_next) + pool[:5]
            state.up_next = new_queue[:5]

    state.started_at = timezone.now()
    state.save()

    # Prepare response data
    current = state.current_track
    _record_live_track_play(request, current)
    live_ai_payload = _get_or_generate_live_ai_payload(current)
    current_track_saved = False
    if request.user.is_authenticated and current:
        current_track_saved = FavouriteSong.objects.filter(
            user=request.user,
            title=str(current.title or '').strip(),
            artist=str(current.artist or '').strip(),
        ).exists()
    up_next_ids = state.up_next
    up_next_tracks = RadioTrack.objects.filter(id__in=up_next_ids)
    up_next_list = sorted(list(up_next_tracks), key=lambda t: up_next_ids.index(t.id))
    up_next_list = [track for track in up_next_list if not _is_generated_voice_track(track)]

    recently_played_ids = state.recently_played
    recently_played_tracks = RadioTrack.objects.filter(id__in=recently_played_ids)
    recently_played_list = sorted(list(recently_played_tracks), key=lambda t: recently_played_ids.index(t.id))
    recently_played_list = [track for track in recently_played_list if not _is_generated_voice_track(track)]

    return JsonResponse({
        'ok': True,
        'current_offset': 0,
        'voice_overlay': None,
        'current_track_saved': current_track_saved,
        'current_track': {
            'id': current.id,
            'title': current.title,
            'artist': current.artist,
            'album_art': current.album_art,
            'audio_url': _build_stream_audio_url(current.audio_url),
            'duration': current.duration,
            'duration_seconds': current.duration_seconds,
        },
        'live_ai_payload': live_ai_payload,
        'up_next': [
            {
                'title': t.title,
                'artist': t.artist,
                'album_art': t.album_art,
                'duration_seconds': int(t.duration_seconds or 0),
            }
            for t in up_next_list[:6]
        ],
        'recently_played': [
            {'title': t.title, 'artist': t.artist, 'album_art': t.album_art}
            for t in recently_played_list[:6]
        ]
    })


def api_live_status(request):
    state, _ = RadioStationState.objects.get_or_create(id=1)
    state = _auto_rotate_station(state)
    current = state.current_track
    current_offset = 0

    up_next_ids = list(state.up_next or [])[:6]
    up_next_tracks = list(RadioTrack.objects.filter(id__in=up_next_ids))
    up_next_tracks = [track for track in up_next_tracks if not _is_generated_voice_track(track)]
    up_next_tracks.sort(key=lambda t: up_next_ids.index(t.id) if t.id in up_next_ids else 999)
    up_next_list = up_next_tracks

    recent_ids = list(state.recently_played or [])[:6]
    recent_tracks = list(RadioTrack.objects.filter(id__in=recent_ids))
    recent_tracks = [track for track in recent_tracks if not _is_generated_voice_track(track)]
    recent_tracks.sort(key=lambda t: recent_ids.index(t.id) if t.id in recent_ids else 999)
    recently_played_list = recent_tracks

    if not current:
        return JsonResponse({'ok': False, 'error': 'No active track'}, status=404)

    return JsonResponse({
        'ok': True,
        'current_offset': current_offset,
        'current_track': {
            'id': current.id,
            'title': current.title,
            'artist': current.artist,
            'album_art': current.album_art,
            'audio_url': _build_stream_audio_url(current.audio_url),
            'duration': current.duration,
            'duration_seconds': current.duration_seconds,
        },
        'up_next': [
            {
                'title': t.title,
                'artist': t.artist,
                'album_art': t.album_art,
                'duration_seconds': int(t.duration_seconds or 0),
            }
            for t in up_next_list
        ],
        'recently_played': [
            {'title': t.title, 'artist': t.artist, 'album_art': t.album_art}
            for t in recently_played_list
        ],
    })


def live_player_popout(request):
    return render(request, 'core/live_popout_player.html')


@csrf_exempt
@require_POST
def api_live_ai_helpful(request):
    try:
        payload = json.loads(request.body or '{}')
    except Exception:
        payload = {}

    track_id = payload.get('track_id')
    if not track_id:
        state, _ = RadioStationState.objects.get_or_create(id=1)
        track_id = state.current_track_id

    if not track_id:
        return JsonResponse({'ok': False, 'error': 'No active track found'}, status=400)

    track = RadioTrack.objects.filter(id=track_id).first()
    if not track:
        return JsonResponse({'ok': False, 'error': 'Track not found'}, status=404)

    normalized = _normalize_live_ai_payload(track.live_ai_payload or {}, track)
    current_count = max(0, int(normalized.get('helpful_count') or 0))
    normalized['helpful_count'] = current_count + 1
    if int(normalized.get('version') or 1) < 2:
        normalized['version'] = 2

    track.live_ai_payload = normalized
    track.live_ai_generated_at = timezone.now()
    track.save(update_fields=['live_ai_payload', 'live_ai_generated_at'])

    return JsonResponse({
        'ok': True,
        'track_id': track.id,
        'helpful_count': normalized['helpful_count'],
    })

def top_cheerleader_badges(request):
    return render(request, 'core/top_cheerleader_badges.html')

def cheerleader_leaderboard(request):
    return render(request, 'core/cheerleader_leaderboard.html')

def legendary_item_claimed(request):
    return render(request, 'core/legendary_item_claimed.html')

def neon_home_variant_1(request):
    return render(request, 'core/neon_home_variant_1.html')

def neon_home_variant_2(request):
    return render(request, 'core/neon_home_variant_2.html')

def test_landing_wow_hero(request):
    featured_article = BlogArticle.objects.order_by('-created_at').first()
    return render(request, 'core/test_landing_wow_hero.html', {
        'featured_article': featured_article,
    })

def celebration_toggle(request):
    return render(request, 'core/celebration_toggle.html')

def profile_personalization_settings(request):
    return render(request, 'core/profile_personalization_settings.html')

def avatar_frame_gallery(request):
    return render(request, 'core/avatar_frame_gallery.html')

def legendary_item_drop(request):
    return render(request, 'core/legendary_item_drop.html')

def gift_received(request):
    return render(request, 'core/gift_received.html')

def k_pop_pulse_idol_emote(request):
    return render(request, 'core/k_pop_pulse_idol_emote.html')

def emote_unlocked(request):
    return render(request, 'core/emote_unlocked.html')

def daily_login_rewards_calendar(request):
    return render(request, 'core/daily_login_rewards_calendar.html')

def streak_recovery(request):
    return render(request, 'core/streak_recovery.html')

def pulse_point_store(request):
    return render(request, 'core/pulse_point_store.html')

def k_pop_pulse_home_neon_variant(request):
    return render(request, 'core/k_pop_pulse_home_neon_variant.html')

def purchase_successful_celebration_modal(request):
    return render(request, 'core/purchase_successful_celebration_modal.html')

def gift_to_a_friend(request):
    return render(request, 'core/gift_to_a_friend.html')

def d_day_comeback_notification(request):
    return render(request, 'core/d_day_comeback_notification.html')

def blog_page(request):
    articles = list(BlogArticle.objects.order_by('-created_at')[:30])
    for article in articles:
        _apply_stream_images_to_article(article)
    cats = list(
        BlogArticle.objects.order_by()
        .values_list('category', flat=True)
        .distinct()
    )
    return render(request, 'core/blog_page.html', {
        'articles': articles,
        'categories': cats,
        'canonical_url': request.build_absolute_uri(reverse('blog_page')),
        'seo_type': 'website',
        'seo_title': 'K-Beats Blog | K-Pop News, Comebacks, and Culture',
        'seo_description': 'Explore K-Pop blog coverage from K-Beats including comeback updates, artist stories, charts, and fan culture.',
    })


def _strip_html_tags(value):
    text = re.sub(r'<[^>]+>', ' ', value or '')
    return re.sub(r'\s+', ' ', text).strip()


def _build_article_meta_title(article):
    base_title = (article.title or '').strip()
    if not base_title:
        return 'K-Beats Blog'
    title = f"{base_title} | K-Beats K-Pop Blog"
    return title[:60].rstrip()


def _build_article_meta_description(article):
    candidates = [
        (article.subtitle or '').strip(),
        _strip_html_tags(article.body_html),
    ]
    for raw in candidates:
        if not raw:
            continue
        text = raw[:157].rstrip()
        if len(raw) > 157:
            text = f"{text}..."
        if len(text) >= 70:
            return text
        return f"{text} | K-Beats K-Pop blog update"
    return "Read the latest K-Pop news, comebacks, and culture features on the K-Beats blog."


def _inject_internal_links(html, article, all_articles):
    body = html or ''
    if not body:
        return body, 0

    # Keep links relevant and not spammy.
    max_total_links = 6
    max_article_links = 4
    links_added = 0
    article_links_added = 0

    site_link_targets = [
        (r'\blive (radio|stream)\b', reverse('live'), 'K-Beats live radio'),
        (r'\bcharts?\b', reverse('charts'), 'K-Pop charts'),
        (r'\bnews\b', reverse('news'), 'K-Pop news feed'),
        (r'\bcomeback(s)?\b', reverse('comeback_timeline'), 'comeback timeline'),
        (r'\bschedule\b', reverse('schedule'), 'radio schedule'),
        (r'\bfan club(s)?\b', reverse('fan_clubs'), 'fan clubs'),
    ]

    article_targets = []
    for candidate in all_articles:
        if candidate.pk == article.pk:
            continue
        phrase = (candidate.title or '').strip()
        if len(phrase) < 8:
            continue
        article_targets.append((phrase, reverse('blog_article_read', kwargs={'slug': candidate.slug})))

    article_targets.sort(key=lambda item: len(item[0]), reverse=True)

    chunks = re.split(r'(<a\b[^>]*>.*?</a>)', body, flags=re.IGNORECASE | re.DOTALL)
    for idx, chunk in enumerate(chunks):
        if links_added >= max_total_links:
            break
        if re.match(r'^<a\b', chunk or '', flags=re.IGNORECASE):
            continue

        segment = chunk
        segment_lower = segment.lower()

        # First add high-intent links to core website pages.
        for pattern, url, title in site_link_targets:
            if links_added >= max_total_links:
                break
            if url.lower() in segment_lower:
                continue
            replacement_pattern = re.compile(pattern, flags=re.IGNORECASE)
            if not replacement_pattern.search(segment):
                continue
            segment = replacement_pattern.sub(
                lambda m: f'<a href="{url}" title="{title}">{m.group(0)}</a>',
                segment,
                count=1,
            )
            links_added += 1
            segment_lower = segment.lower()

        # Then connect to related articles.
        for phrase, url in article_targets:
            if links_added >= max_total_links or article_links_added >= max_article_links:
                break
            if url.lower() in segment_lower:
                continue
            phrase_pattern = re.compile(rf'(?<!\w){re.escape(phrase)}(?!\w)', flags=re.IGNORECASE)
            if not phrase_pattern.search(segment):
                continue
            segment = phrase_pattern.sub(
                lambda m: (
                    f'<a href="{url}" title="Read: {phrase}" rel="internal">{m.group(0)}</a>'
                ),
                segment,
                count=1,
            )
            links_added += 1
            article_links_added += 1
            segment_lower = segment.lower()

        chunks[idx] = segment

    return ''.join(chunks), links_added


def blog_article_read(request, slug):
    from django.shortcuts import get_object_or_404
    article = get_object_or_404(BlogArticle, slug=slug)
    _apply_stream_images_to_article(article)
    related = (
        BlogArticle.objects
        .filter(category=article.category)
        .exclude(pk=article.pk)[:3]
    )
    related = list(related)
    for related_article in related:
        _apply_stream_images_to_article(related_article)
    canonical_url = request.build_absolute_uri(
        reverse('blog_article_read', kwargs={'slug': article.slug})
    )
    meta_title = _build_article_meta_title(article)
    meta_description = _build_article_meta_description(article)
    return render(request, 'core/blog_article.html', {
        'article': article,
        'related': related,
        'canonical_url': canonical_url,
        'meta_title': meta_title,
        'meta_description': meta_description,
        'seo_type': 'article',
        'seo_title': meta_title,
        'seo_description': meta_description,
    })


def _fetch_blog_image(title, category, excerpt='', variant=1):
    """Use DeepSeek for keywords, fetch via Serper, upload to Cloudinary."""
    import cloudinary
    import cloudinary.uploader
    from urllib.parse import urlparse
    serper_key = getattr(settings, 'SERPER_API_KEY', '')
    if not serper_key:
        return ''

    def _is_valid_image_candidate(url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        host = (parsed.netloc or '').lower()
        blocked_hosts = (
            'lookaside.instagram.com',
            'lookaside.fbsbx.com',
            'www.tiktok.com',
            'tiktok.com',
        )
        if any(host.endswith(h) for h in blocked_hosts):
            return False
        try:
            check_resp = requests.get(
                url,
                timeout=10,
                allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0'},
                stream=True,
            )
            if check_resp.status_code >= 400:
                return False
            content_type = (check_resp.headers.get('content-type') or '').lower()
            return content_type.startswith('image/')
        except Exception:
            return False

    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
    cloud_key = getattr(settings, 'CLOUDINARY_API_KEY', '')
    cloud_secret = getattr(settings, 'CLOUDINARY_API_SECRET', '')
    can_upload_to_cloudinary = bool(cloud_name and cloud_key and cloud_secret)
    if can_upload_to_cloudinary:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=cloud_key,
            api_secret=cloud_secret,
            secure=True,
        )
    else:
        logger.warning(
            "[blog image %d] Cloudinary credentials incomplete; using source image URL fallback.",
            variant,
        )

    # Ask DeepSeek for concise image search keywords
    if variant == 1:
        kw_prompt = (
            f"Give me 2-4 concise English search keywords for finding a "
            f"relevant news image on Google for a K-Pop article. "
            f"Return ONLY the keywords separated by spaces, nothing else.\n\n"
            f"Title: {title}\nCategory: {category}\nExcerpt: {excerpt[:200]}"
        )
    elif variant == 3:
        kw_prompt = (
            f"Give me 2-4 concise English search keywords for an image showing "
            f"fans, merchandise, or cultural impact related to a K-Pop article "
            f"about: {title}. Category: {category}.\n"
            f"Return ONLY the keywords separated by spaces, nothing else.\n"
            f"Examples: 'kpop fans lightsticks concert', 'kpop album merchandise', "
            f"'kpop street fashion Seoul'"
        )
    else:
        kw_prompt = (
            f"Give me 2-4 concise English search keywords for a second "
            f"atmospheric/mood image (not the same subject) that complements "
            f"a K-Pop article about: {title}. Category: {category}.\n"
            f"Return ONLY the keywords separated by spaces, nothing else.\n"
            f"Examples: 'kpop concert stage lights', 'kpop fans crowd', "
            f"'music recording studio microphone'"
        )
    try:
        keywords = _chat(
            kw_prompt,
            system="You output only image search keywords, nothing else.",
        ).strip().strip('"').strip("'")
        logger.info(
            "[blog image %d] keywords for %r -> %r", variant, title, keywords
        )
    except Exception:
        if variant == 1:
            keywords = f"kpop {category}"
        elif variant == 3:
            keywords = "kpop fans lightsticks"
        else:
            keywords = "kpop concert stage"

    if not keywords:
        keywords = "kpop performance stage"

    # Build a stable Cloudinary public_id for this image slot
    from django.utils.text import slugify
    title_slug = slugify(title)[:60]
    public_id = f"ksync/blog/{title_slug}/img{variant}"

    # Search via Serper.dev Google Images, then upload to Cloudinary
    fallback = 'kpop concert stage'
    for query in (keywords, fallback):
        try:
            resp = requests.post(
                'https://google.serper.dev/images',
                json={'q': query, 'num': 5},
                headers={
                    'X-API-KEY': serper_key,
                    'Content-Type': 'application/json',
                },
                timeout=15,
            )
            if resp.status_code == 200:
                items = resp.json().get('images', [])
                for item in items:
                    img_url = item.get('imageUrl', '')
                    if not img_url:
                        continue
                    if not _is_valid_image_candidate(img_url):
                        continue
                    if not can_upload_to_cloudinary:
                        logger.info(
                            "[blog image %d] using direct image URL fallback: %r",
                            variant, img_url,
                        )
                        return img_url

                    # Download and upload to Cloudinary for stable hosting
                    try:
                        result = cloudinary.uploader.upload(
                            img_url,
                            public_id=public_id,
                            overwrite=False,
                            resource_type='image',
                            timeout=20,
                        )
                        cdn_url = result.get('secure_url', '')
                        if cdn_url:
                            logger.info(
                                "[blog image %d] uploaded to Cloudinary: %r",
                                variant, cdn_url,
                            )
                            return cdn_url
                    except Exception as upload_err:
                        logger.warning(
                            "[blog image %d] Cloudinary upload failed "
                            "for %r: %s - trying next item",
                            variant, img_url, upload_err,
                        )
                        continue
        except Exception:
            pass
    return ''


def _do_blog_generate():
    """
    Core blog generation logic - fetch RSS articles and write new ones via AI.
    Called by both the blog_generate view and the background scheduler job.
    Returns the number of articles created.
    """
    import re
    from difflib import SequenceMatcher
    from django.utils.text import slugify

    def _title_too_similar_to_db(new_title, db_titles, threshold=0.70):
        """Return True if new_title is too similar to any already-published title."""
        nt = new_title.lower()
        for existing in db_titles:
            ratio = SequenceMatcher(None, nt, existing.lower()).ratio()
            if ratio >= threshold:
                return True
        return False

    # Force a fresh fetch (bypass cache) so the scheduler always gets new items
    _news_cache['ts'] = 0
    articles = _fetch_kpop_news()
    created = 0

    # Gather existing article slugs/source_titles for duplicate detection + SEO links
    existing_articles = list(
        BlogArticle.objects.values('slug', 'title', 'source_title').order_by('-created_at')[:50]
    )
    db_titles = [a['source_title'] if a.get('source_title') else a['title'] for a in existing_articles]

    for item in articles:
        title = item.get('title', '').strip()
        if not title:
            continue

        base_slug = slugify(title)[:180]
        # Exact slug match check
        if BlogArticle.objects.filter(slug=base_slug).exists():
            continue

        # Similarity check against all published titles to prevent near-duplicates
        if _title_too_similar_to_db(title, db_titles):
            logger.info("[blog] Skipping near-duplicate DB title: %r", title)
            continue

        source = item.get('source', '')
        link = item.get('link', '')
        category = item.get('category', 'News')
        excerpt = item.get('excerpt', '')

        # Build inter-linking hints from already-existing articles
        internal_links_hint = ''
        if existing_articles:
            link_refs = ', '.join(
                f'"{a["title"]}" at /blog/{a["slug"]}/'
                for a in existing_articles[:5]
            )
            internal_links_hint = (
                f"\n\nFor SEO inter-linking, naturally reference and link to "
                f"1-2 of these existing K-Beats articles where relevant "
                f"(use <a href=\"/blog/SLUG/\">Title</a> format): {link_refs}"
            )

        site_links_hint = (
            "\nAlso include 1-2 natural links to K-Beats internal pages using "
            "<a href=\"/idols/\">our Artists page</a>, "
            "<a href=\"/charts/\">our Charts page</a>, or "
            "<a href=\"/news/\">our News page</a> where contextually appropriate."
        )

        # â”€â”€ DeepSeek Reasoner article â”€â”€
        prompt = (
            f"Write an original, in-depth K-Pop news article based on this headline:\n\n"
            f"Title: {title}\n"
            f"Source: {source}\n"
            f"Summary: {excerpt}\n\n"
            f"Write as a professional K-Pop journalist for K-Beats, a major K-Pop media outlet. "
            f"The article MUST be at least 1,500 words. Make it deeply informative, engaging, and comprehensive.\n\n"
            f"Structure your response EXACTLY as follows:\n"
            f"TITLE: (a completely new, engaging, and original headline)\n"
            f"SUBTITLE: (one catchy subtitle line)\n"
            f"---\n"
            f"(article body in HTML)\n\n"
            f"HTML Formatting Rules:\n"
            f"- Use <h2> tags for major section headings (aim for 3-4 per article)\n"
            f"- Use <h3> tags for sub-section headings within major sections\n"
            f"- Use <p> for all paragraphs\n"
            f"- Use <strong> to bold key terms and artist names\n"
            f"- Use <em> for stylistic emphasis\n"
            f"- Use <blockquote> for notable quotes or standout statements\n"
            f"- Use <ul>/<ol>/<li> for lists where appropriate\n"
            f"- Do NOT use <h1> tags (the page already has an h1 title)\n\n"
            f"Content Sections Required:\n"
            f"1. Opening - hook the reader and introduce the story\n"
            f"2. Background - artist/group history and context\n"
            f"3. The News - detailed breakdown of the main story\n"
            f"4. Fan & Community Reaction - what fans are saying\n"
            f"5. Industry Analysis - impact and significance\n"
            f"6. What's Next - forward-looking conclusion\n\n"
            f"Rules:\n"
            f"- Write completely original content, do NOT copy the source\n"
            f"- Total length: minimum 1,500 words\n"
            f"- Do NOT include the article title in the body\n"
            f"- Do NOT mention AI anywhere in the article\n"
            f"- Write as a human journalist, not an AI\n"
            f"{internal_links_hint}"
            f"{site_links_hint}"
        )

        try:
            raw = _chat_reasoner(
                prompt,
                system=(
                    "You are a senior K-Pop journalist at K-Beats, a leading K-Pop news outlet. "
                    "Write engaging, original long-form articles with insider knowledge. "
                    "Always use HTML tags for formatting as specified. "
                    "Never mention AI, never reveal you are an AI."
                ),
            )
        except Exception:
            continue

        subtitle = ''
        generated_title = title
        body = raw
        if '---' in raw:
            header, body = raw.split('---', 1)
            for line in header.strip().splitlines():
                if line.upper().startswith('TITLE:'):
                    generated_title = line.split(':', 1)[1].strip().strip('"').strip("'")
                elif line.upper().startswith('SUBTITLE:'):
                    subtitle = line.split(':', 1)[1].strip()
                    # We don't break here so we can find both TITLE and SUBTITLE


        body = body.strip()
        if not body.startswith('<'):
            paras = body.split('\n\n')
            body = ''.join(
                f'<p>{p.strip()}</p>' for p in paras if p.strip()
            )

        word_count = len(re.sub(r'<[^>]+>', '', body).split())
        reading_time = max(1, word_count // 200)

        # â”€â”€ Fetch image via Serper â”€â”€
        try:
            image_1 = _fetch_blog_image(title, category, excerpt, variant=1)
        except Exception as e:
            logger.exception("Blog image_1 fetch failed for title=%r: %s", title, e)
            image_1 = ''

        article = BlogArticle.objects.create(
            slug=base_slug,
            title=generated_title,
            subtitle=subtitle,
            category=category,
            source_title=title,
            source_url=link,
            source_name=source,
            image=image_1,
            body_html=body,
            reading_time=reading_time,
        )
        created += 1
        db_titles.append(title)

        # Post to Facebook Page as a scheduled post
        try:
            _post_to_facebook_draft(article)
        except Exception as e:
            logger.warning("[facebook] Draft post failed for %r: %s", title, e)

        # Post to Instagram
        try:
            _post_to_instagram(article)
        except Exception as e:
            logger.warning("[instagram] Post failed for %r: %s", title, e)

        # Optional immediate X posting. The scheduled X queue handles the
        # normal publishing cadence, so this stays off unless explicitly enabled.
        if getattr(settings, 'X_POST_ON_CREATE_ENABLED', False):
            try:
                _post_to_x(article)
            except Exception as e:
                logger.warning("[x] Post failed for %r: %s", title, e)
        else:
            logger.info("[x] Immediate posting disabled - article queued for scheduler for %r", title)

        # Post to Pinterest
        try:
            _post_to_pinterest(article)
        except Exception as e:
            logger.warning("[pinterest] Post failed for %r: %s", title, e)

        # Keep inter-linking list current for subsequent articles
        existing_articles.append({'slug': base_slug, 'title': title})

    logger.info("[blog] Auto-generate run complete - created %d article(s).", created)
    return created


def _post_to_facebook_draft(article, scheduled_unix_ts=None):
    """
    Schedules a newly created BlogArticle on the connected Facebook Page.
    The post appears in Meta Business Suite -> Content -> Scheduled.
    Defaults to 24 hours from now if no timestamp is provided.
    Requires FACEBOOK_PAGE_ID and FACEBOOK_PAGE_ACCESS_TOKEN in settings.
    """
    import time as _time

    page_id = getattr(settings, 'FACEBOOK_PAGE_ID', '')
    token = getattr(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', '')
    if not page_id or not token:
        logger.debug("[facebook] No credentials configured - skipping scheduled post.")
        return

    if article.facebook_posted_at or article.facebook_post_id:
        logger.debug("[facebook] Already handled article %r - skipping.", article.slug)
        return

    # Default: schedule 1 hour from now
    if scheduled_unix_ts is None:
        scheduled_unix_ts = int(_time.time()) + 3600

    article_url = _social_article_url(article, source='facebook')
    hook = _social_hook(article)
    plain_excerpt = _article_opening_excerpt(article, max_chars=400)
    hashtags = ' '.join(_social_hashtags('facebook', article))

    # Construct a link-first message so Facebook creates a proper article preview.
    message = (
        f"{hook} {article.title}\n\n"
        f"{plain_excerpt}\n\n"
        f"Read more: {article_url}\n\n"
        f"{hashtags}"
    )

    payload = {
        'message': message,
        'link': article_url,
        'published': False,
        'scheduled_publish_time': scheduled_unix_ts,
    }

    try:
        resp = requests.post(
            f'https://graph.facebook.com/v22.0/{page_id}/feed',
            data=payload,
            params={'access_token': token},
            timeout=20,
        )
        result = resp.json()
        if resp.status_code == 200 and 'id' in result:
            # We don't update facebook_posted_at here because it's scheduled, not posted.
            # But the model uses it to track if we've handled it. 
            # Let's update the ID so we can track it.
            BlogArticle.objects.filter(pk=article.pk).update(
                facebook_post_id=result['id'],
            )
            logger.info(
                "[facebook] Scheduled link post created for %r - post id: %s",
                article.title, result['id'],
            )
        else:
            logger.warning(
                "[facebook] Scheduled post failed for %r - status=%s response=%s",
                article.title, resp.status_code, result,
            )
    except Exception as e:
        logger.warning("[facebook] Request error for %r: %s", article.title, e)


def _comment_on_live_facebook_posts():
    """
    Add a single homepage comment to Facebook posts after they go live.
    Returns the number of new comments created.
    """
    if not getattr(settings, 'FACEBOOK_HOMEPAGE_COMMENT_ENABLED', False):
        return 0

    token = getattr(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', '')
    homepage_comment = _normalize_social_text(
        getattr(settings, 'FACEBOOK_HOMEPAGE_COMMENT_TEXT', '')
    ).strip()
    if not token or not homepage_comment:
        return 0

    candidates = list(BlogArticle.objects.filter(
        facebook_post_id__gt='',
        facebook_homepage_comment_id='',
    ).order_by('created_at')[:100])
    if not candidates:
        return 0

    page_id = getattr(settings, 'FACEBOOK_PAGE_ID', '')
    if not page_id:
        return 0

    try:
        published_resp = requests.get(
            f'https://graph.facebook.com/v22.0/{page_id}/published_posts',
            params={
                'access_token': token,
                'fields': 'id',
                'limit': 100,
            },
            timeout=20,
        )
        published_data = published_resp.json()
        if published_resp.status_code != 200:
            logger.warning(
                "[facebook] Could not load published posts - status=%s response=%s",
                published_resp.status_code, published_data,
            )
            return 0
        published_ids = {
            str(item.get('id') or '').strip()
            for item in published_data.get('data', [])
            if str(item.get('id') or '').strip()
        }
    except Exception as exc:
        logger.warning("[facebook] Could not load published posts: %s", exc)
        return 0

    created_comments = 0
    for article in candidates:
        raw_post_id = str(article.facebook_post_id or '').strip()
        post_id = raw_post_id
        if post_id and '_' not in post_id and page_id:
            post_id = f"{page_id}_{post_id}"
        if not post_id:
            continue

        if post_id not in published_ids:
            continue

        try:
            comment_resp = requests.post(
                f'https://graph.facebook.com/v22.0/{post_id}/comments',
                data={'message': homepage_comment},
                params={'access_token': token},
                timeout=15,
            )
            comment_data = comment_resp.json()
            if comment_resp.status_code == 200 and comment_data.get('id'):
                BlogArticle.objects.filter(pk=article.pk).update(
                    facebook_posted_at=timezone.now(),
                    facebook_homepage_comment_id=comment_data['id'],
                    facebook_homepage_commented_at=timezone.now(),
                )
                created_comments += 1
                logger.info(
                    "[facebook] Added homepage comment for %r - comment id: %s",
                    article.title, comment_data['id'],
                )
            else:
                logger.warning(
                    "[facebook] Homepage comment failed for %r - status=%s response=%s",
                    article.title, comment_resp.status_code, comment_data,
                )
        except Exception as exc:
            logger.warning(
                "[facebook] Homepage comment request error for %r: %s",
                article.title, exc,
            )

    return created_comments


def _post_to_instagram(article):
    """
    Publishes the article as an Instagram post via the Facebook Graph API.
    Requires the Instagram Business account to be linked to the Facebook Page.
    Enable by setting INSTAGRAM_POST_ENABLED=true in settings/env.
    """
    if not getattr(settings, 'INSTAGRAM_POST_ENABLED', False):
        return

    page_id = getattr(settings, 'FACEBOOK_PAGE_ID', '')
    token = getattr(settings, 'FACEBOOK_PAGE_ACCESS_TOKEN', '')
    if not page_id or not token:
        return

    if not article.image:
        logger.warning("[instagram] No image for %r - skipping.", article.title)
        return

    # Resolve linked Instagram Business Account ID
    resp = requests.get(
        f'https://graph.facebook.com/v19.0/{page_id}',
        params={'fields': 'instagram_business_account', 'access_token': token},
        timeout=10,
    )
    ig_id = resp.json().get('instagram_business_account', {}).get('id')
    if not ig_id:
        logger.warning("[instagram] No linked Instagram Business account.")
        return

    plain = _article_opening_excerpt(article, max_chars=300)
    hashtags = ' '.join(_social_hashtags('instagram', article))
    hook = _social_hook(article)
    caption = (
        f"{hook}\n\n"
        f"{article.title}\n\n"
        f"{plain}\n\n"
        f"Read the full article via link in bio.\n\n"
        f"{hashtags}"
    )

    # Step 1: Create media container
    container = requests.post(
        f'https://graph.facebook.com/v19.0/{ig_id}/media',
        data={'image_url': article.image, 'caption': caption,
              'access_token': token},
        timeout=15,
    ).json()
    if 'id' not in container:
        logger.warning("[instagram] Container creation failed: %s", container)
        return

    # Step 2: Publish the container
    result = requests.post(
        f'https://graph.facebook.com/v19.0/{ig_id}/media_publish',
        data={'creation_id': container['id'], 'access_token': token},
        timeout=15,
    ).json()
    if 'id' in result:
        logger.info("[instagram] Posted %r - id: %s", article.title, result['id'])
    else:
        logger.warning("[instagram] Publish failed: %s", result)


def _article_opening_excerpt(article, max_chars=180):
    """Extract a clean snippet from the article opening paragraph."""
    import html as _html
    import re as _re

    body_html = article.body_html or ''
    match = _re.search(
        r'<p[^>]*>(.*?)</p>', body_html, flags=_re.IGNORECASE | _re.DOTALL
    )

    if match:
        raw = _re.sub(r'<[^>]+>', '', match.group(1))
    elif article.subtitle:
        raw = article.subtitle
    else:
        raw = _re.sub(r'<[^>]+>', '', body_html)

    text = _normalize_social_text(_html.unescape(' '.join((raw or '').split())))
    if not text:
        return ''
    if len(text) <= max_chars:
        return text

    cut = text[:max_chars]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip('.,;:! ') + '...'


def _social_article_url(article, source):
    """Build article URL with source-specific UTM tags."""
    import urllib.parse as _up

    site_url = getattr(settings, 'SITE_URL', 'https://kbeatsradio.co.uk')
    base = f"{site_url.rstrip('/')}/blog/{article.slug}/"
    qs = _up.urlencode({
        'utm_source': source,
        'utm_medium': 'social',
        'utm_campaign': 'auto_blog',
    })
    return f"{base}?{qs}"


def _social_hashtags(platform, article):
    """Return platform-specific hashtag list."""
    tags = [
        '#KPop', '#KPopNews', '#KPopUpdate', '#KBeats', '#KBeatsRadio',
        '#Hallyu', '#KoreanMusic', '#KPopWorld', '#KPopFandom',
        '#IdolNews', '#KPopLife', '#KoreanWave', '#KPopIdol',
    ]

    cat = (article.category or '').lower()
    if 'comeback' in cat:
        tags.extend(['#Comeback', '#NewRelease', '#KPopComeback'])
    elif 'review' in cat:
        tags.extend(['#KPopReview', '#MusicReview', '#AlbumReview'])
    elif 'chart' in cat:
        tags.extend(['#KPopCharts', '#MelonChart', '#Billboard', '#MusicCharts'])
    else:
        tags.extend(['#KMusic', '#KPopDaily', '#Trending'])

    if platform in {'facebook', 'instagram'}:
        tags.extend(['#KPopCommunity', '#KPopStan', '#ExploringKPop'])

    # preserve order, remove duplicates
    deduped = []
    for tag in tags:
        if tag not in deduped:
            deduped.append(tag)
    return deduped


def _social_hook(article):
    """Generate a short hook line for social posts."""
    cat = (article.category or 'news').strip()
    if cat.lower() == 'review':
        return "New Review:"
    if cat.lower() == 'comeback':
        return "Comeback Alert:"
    return "New K-Pop Update:"


def _x_teaser_line(article, max_chars=120):
    """Generate an X-specific teaser line in a conversational style."""
    excerpt = _article_opening_excerpt(article, max_chars=max_chars)
    if not excerpt:
        return "In a move that has fans talking, this story is one to watch."

    # Avoid doubling if the excerpt already starts similarly
    low = excerpt.lower()
    if low.startswith('in a move') or low.startswith('as '):
        return excerpt

    if excerpt and excerpt[0].isalpha():
        excerpt = excerpt[0].lower() + excerpt[1:]
    return f"In a move that {excerpt}"


def _x_text_length(text):
    """Approximate X character counting (URLs count as 23 chars)."""
    import re as _re

    urls = _re.findall(r'https?://\S+', text)
    length = len(text)
    for u in urls:
        length -= len(u)
        length += 23
    return length


def _x_compose_text(title_text, teaser, article_url, hashtags):
    """Compose tweet text close to 280 chars using URL-aware counting."""
    core = f"{title_text}\n\n{teaser}\n\n{article_url}\n\n{hashtags}" if teaser else (
        f"{title_text}\n\n{article_url}\n\n{hashtags}"
    )
    if _x_text_length(core) <= 280:
        return core

    trimmed = teaser
    while trimmed and _x_text_length(
        f"{title_text}\n\n{trimmed}\n\n{article_url}\n\n{hashtags}"
    ) > 280:
        trimmed = trimmed[:-2].rstrip('.,;:! ') + '...' if len(trimmed) > 2 else ''

    if trimmed:
        return f"{title_text}\n\n{trimmed}\n\n{article_url}\n\n{hashtags}"
    return f"{title_text}\n\n{article_url}\n\n{hashtags}"


def _x_oauth1_auth_header(
    method,
    url,
    api_key,
    api_secret,
    access_token,
    access_secret,
    extra_params=None,
):
    """Build OAuth1 Authorization header for X API requests."""
    import hmac
    import hashlib
    import base64
    import secrets as _secrets
    import time as _time

    oauth_params = {
        'oauth_consumer_key': api_key,
        'oauth_nonce': _secrets.token_hex(16),
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': str(int(_time.time())),
        'oauth_token': access_token,
        'oauth_version': '1.0',
    }

    sig_params = dict(oauth_params)
    if extra_params:
        sig_params.update(extra_params)

    import urllib.parse as _up
    param_string = '&'.join(
        f"{_up.quote(str(k), safe='')}={_up.quote(str(v), safe='')}"
        for k, v in sorted(sig_params.items())
    )
    base_string = (
        method.upper()
        + '&'
        + _up.quote(url, safe='')
        + '&'
        + _up.quote(param_string, safe='')
    )
    signing_key = (
        _up.quote(api_secret, safe='')
        + '&'
        + _up.quote(access_secret, safe='')
    )
    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth_params['oauth_signature'] = signature

    return 'OAuth ' + ', '.join(
        f'{_up.quote(k, safe="")}="{_up.quote(str(v), safe="")}"'
        for k, v in sorted(oauth_params.items())
    )


def _post_to_x(article):
    """
    Posts a tweet to X (Twitter) via API v2 using OAuth 1.0a.
    Requires X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET.
    """
    if not getattr(settings, 'X_POST_ENABLED', False):
        logger.debug("[x] Posting disabled via X_POST_ENABLED - skipping.")
        return

    api_key = getattr(settings, 'X_API_KEY', '')
    api_secret = getattr(settings, 'X_API_SECRET', '')
    access_token = getattr(settings, 'X_ACCESS_TOKEN', '')
    access_secret = getattr(settings, 'X_ACCESS_TOKEN_SECRET', '')
    if not all([api_key, api_secret, access_token, access_secret]):
        logger.debug("[x] Credentials not configured - skipping.")
        return

    if article.x_posted_at:
        logger.debug("[x] Already posted article %r - skipping.", article.slug)
        return

    article_url = _social_article_url(article, source='x')
    title = article.title[:200]
    hook = _social_hook(article)
    hashtags = ' '.join(_social_hashtags('x', article))

    title_text = f"{hook}: {title}"
    if len(title_text) > 110:
        title_text = title_text[:109].rstrip() + 'â€¦'

    # Reserve room dynamically with URL-aware length counting.
    base_len = _x_text_length(f"{title_text}\n\n{article_url}\n\n{hashtags}")
    teaser_budget = max(0, 280 - base_len - 2)  # 2 for extra newline separator
    excerpt = _x_teaser_line(article, max_chars=max(40, min(220, teaser_budget)))
    tweet_text = _x_compose_text(title_text, excerpt, article_url, hashtags)

    media_id = None
    if article.image:
        try:
            img = requests.get(article.image, timeout=20)
            if img.status_code == 200 and img.content:
                upload_url = 'https://upload.twitter.com/1.1/media/upload.json'
                upload_auth = _x_oauth1_auth_header(
                    'POST',
                    upload_url,
                    api_key,
                    api_secret,
                    access_token,
                    access_secret,
                )
                upload_resp = requests.post(
                    upload_url,
                    headers={'Authorization': upload_auth},
                    files={
                        'media': (
                            'article.jpg',
                            img.content,
                            img.headers.get('Content-Type', 'image/jpeg'),
                        )
                    },
                    timeout=30,
                )
                upload_result = upload_resp.json()
                media_id = upload_result.get('media_id_string') or (
                    str(upload_result.get('media_id'))
                    if upload_result.get('media_id')
                    else None
                )
                if not media_id:
                    logger.warning(
                        "[x] Media upload failed (tweeting text-only): %s",
                        upload_result,
                    )
            else:
                logger.warning(
                    "[x] Could not fetch article image (tweeting text-only): %s",
                    article.image,
                )
        except Exception as e:
            logger.warning(
                "[x] Media upload request failed (tweeting text-only): %s",
                e,
            )

    url = 'https://api.twitter.com/2/tweets'
    auth_header = _x_oauth1_auth_header(
        'POST',
        url,
        api_key,
        api_secret,
        access_token,
        access_secret,
    )

    payload = {'text': tweet_text}
    if media_id:
        payload['media'] = {'media_ids': [media_id]}

    result = requests.post(
        url,
        headers={
            'Authorization': auth_header,
            'Content-Type': 'application/json',
        },
        json=payload,
        timeout=15,
    ).json()

    if 'data' in result:
        BlogArticle.objects.filter(pk=article.pk).update(
            x_post_id=result['data']['id'],
            x_posted_at=timezone.now(),
        )
        logger.info("[x] Tweeted %r - id: %s", article.title, result['data']['id'])
    else:
        logger.warning("[x] Tweet failed: %s", result)


def _post_next_article_to_x():
    """Post the oldest unpublished article to X and return True when sent."""
    if not getattr(settings, 'X_POST_ENABLED', False):
        logger.debug("[x] Scheduler posting disabled via X_POST_ENABLED - skipping.")
        return False

    article = (
        BlogArticle.objects
        .filter(x_posted_at__isnull=True)
        .order_by('created_at')
        .first()
    )
    if not article:
        logger.debug("[x] No queued articles found for scheduler.")
        return False

    if article.x_post_id:
        logger.debug("[x] Article %r already has an X post id - skipping.", article.slug)
        return False

    _post_to_x(article)
    article.refresh_from_db(fields=['x_posted_at'])
    return bool(article.x_posted_at)


def _post_to_pinterest(article):
    """
    Creates a Pinterest Pin for the article.
    Requires PINTEREST_ACCESS_TOKEN and PINTEREST_BOARD_ID in settings.
    """
    access_token = getattr(settings, 'PINTEREST_ACCESS_TOKEN', '')
    board_id = getattr(settings, 'PINTEREST_BOARD_ID', '')
    if not access_token or not board_id:
        logger.debug("[pinterest] Credentials not configured - skipping.")
        return

    if article.pinterest_posted_at:
        logger.debug("[pinterest] Already posted article %r - skipping.", article.slug)
        return

    if not article.image:
        logger.warning("[pinterest] No image for %r - skipping.", article.title)
        return

    article_url = _social_article_url(article, source='pinterest')
    plain = _article_opening_excerpt(article, max_chars=500)

    result = requests.post(
        'https://api.pinterest.com/v5/pins',
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        json={
            'title': article.title,
            'description': plain,
            'link': article_url,
            'board_id': board_id,
            'media_source': {
                'source_type': 'image_url',
                'url': article.image,
            },
        },
        timeout=15,
    ).json()

    if 'id' in result:
        BlogArticle.objects.filter(pk=article.pk).update(
            pinterest_post_id=result['id'],
            pinterest_posted_at=timezone.now(),
        )
        logger.info("[pinterest] Pin created for %r - id: %s",
                    article.title, result['id'])
    else:
        logger.warning("[pinterest] Pin failed: %s", result)


def blog_generate(request):
    """Manual trigger: generate blog articles from RSS feeds and redirect."""
    from django.shortcuts import redirect
    _do_blog_generate()
    return redirect('news')


def blog_internal_link_pass(request):
    """
    Post-generation pass: scan every article's body_html and inject
    <a href="/blog/SLUG/"> hyperlinks wherever sibling article titles
    are naturally mentioned in the text.
    """
    gate = _staff_only_json(request)
    if gate:
        return gate

    all_articles = list(BlogArticle.objects.order_by('-created_at'))
    if len(all_articles) < 2:
        return JsonResponse({'ok': True, 'updated': 0, 'message': 'Not enough articles for linking.'})

    updated = 0
    total_links_added = 0
    for article in all_articles:
        updated_html, links_added = _inject_internal_links(article.body_html, article, all_articles)
        if links_added <= 0 or updated_html == (article.body_html or ''):
            continue
        BlogArticle.objects.filter(pk=article.pk).update(body_html=updated_html)
        updated += 1
        total_links_added += links_added

    return JsonResponse({
        'ok': True,
        'updated_articles': updated,
        'total_links_added': total_links_added,
        'scanned_articles': len(all_articles),
    })


def new_release_spotlight(request):
    return render(request, 'core/new_release_spotlight.html')

def streaming_party_chat(request):
    return render(request, 'core/streaming_party_chat.html')

def confetti_rain(request):
    return render(request, 'core/confetti_rain.html')

# â”€â”€ AI Endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@csrf_exempt
@require_POST
def ai_generate_image(request):
    """
    Calls Getimg.ai's Flux Schnell text-to-image API.
    Expects POST JSON data: {"prompt": "..."}
    Optional: width, height, steps
    """
    try:
        data = json.loads(request.body)
        prompt = data.get('prompt')
        
        if not prompt:
            return JsonResponse({'success': False, 'error': 'No prompt provided.'})
            
        url = "https://api.getimg.ai/v1/flux-schnell/text-to-image"
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {settings.GETIMG_API_KEY}"
        }
        
        payload = {
            "prompt": prompt,
            "width": data.get('width', 1024),
            "height": data.get('height', 1024),
            "steps": data.get('steps', 4),
            "response_format": "b64"
        }
        
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        if response.status_code == 200:
            return JsonResponse({'success': True, 'image': response_data.get('image')})
        else:
            return JsonResponse({'success': False, 'error': response_data})
            
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@csrf_exempt
@require_POST
def ai_like(request):
    """
    Save a liked song to the session catalogue.
    Returns AI group/artist suggestions once the user has 2+ likes.
    """
    try:
        data   = json.loads(request.body)
        song   = data.get('song', '').strip()
        artist = data.get('artist', '').strip()

        if not song or not artist:
            return JsonResponse({'error': 'Missing song or artist'}, status=400)

        # Persist liked songs in session
        liked = request.session.get('liked_songs', [])
        entry = {'song': song, 'artist': artist}
        if entry not in liked:
            liked.append(entry)
        request.session['liked_songs'] = liked
        request.session.modified = True

        suggestions = None
        if len(liked) >= 2:
            liked_text = ', '.join([f"{s['song']} by {s['artist']}" for s in liked])
            prompt = (
                f"A K-Pop fan has liked these songs on a live radio station: {liked_text}. "
                f"Based on their taste, recommend 4 K-Pop groups or solo artists they would love. "
                f"For each, give the name and one sentence explaining why they'd enjoy it. "
                f"Return as a JSON array: "
                f'[{{"name": "Group Name", "reason": "..."}}]'
            )
            raw = _chat(prompt)
            # Extract JSON from the response
            start = raw.find('[')
            end   = raw.rfind(']') + 1
            suggestions = json.loads(raw[start:end]) if start != -1 else []

        return JsonResponse({
            'liked_count': len(liked),
            'liked_songs': liked,
            'suggestions': suggestions,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def ai_commentary(request):
    """
    Generate a short AI DJ blurb for the currently playing song.
    """
    try:
        data   = json.loads(request.body)
        song   = data.get('song', 'Unknown')
        artist = data.get('artist', 'Unknown')
        prev   = data.get('previous', [])  # list of recent songs

        prev_text = (', '.join([f"{s['song']} by {s['artist']}" for s in prev[-3:]])
                     if prev else 'nothing yet')

        prompt = (
            f"You are an enthusiastic K-Pop radio DJ. Write a punchy 1-2 sentence "
            f"on-air commentary introducing '{song}' by {artist}. "
            f"Previous songs included: {prev_text}. "
            f"Be energetic, use emojis sparingly, keep it under 50 words. "
            f"Sound like a real radio host, not a robot."
        )
        blurb = _chat(prompt, system="You are a charismatic K-Pop radio DJ host.")
        return JsonResponse({'blurb': blurb})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def ai_theme(request):
    """
    Generate a colour palette that matches the mood of the current song.
    Premium users only (enforced on frontend; add auth check for production).
    """
    try:
        data   = json.loads(request.body)
        song   = data.get('song', 'Unknown')
        artist = data.get('artist', 'Unknown')

        prompt = (
            f"The K-Pop song '{song}' by {artist} is playing on a live radio page. "
            f"Generate a 3-colour neon/dark palette that matches the song's mood and energy. "
            f"Return ONLY valid JSON in this exact format - no markdown, no explanation: "
            f'{{"primary": "#hexcode", "secondary": "#hexcode", "accent": "#hexcode", "mood": "one word"}}'
        )
        raw = _chat(prompt, system="You are a UI designer who picks colour palettes for K-Pop music apps.")
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        palette = json.loads(raw[start:end])
        return JsonResponse(palette)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def ai_generate_ranking(request):
    """
    Generate the definitive K-Pop power ranking (Top 10 tracks) using Deepseek.
    """
    prompt = (
        "Generate a definitive K-Pop power ranking of the Top 10 tracks for the current week. "
        "Synthesize high-velocity data from three pillars: "
        "1. Digital Impact (Streaming - 50% Weight): Circle Chart (Digital), MelOn Top 100, Spotify Daily Top Songs South Korea, YouTube Music. "
        "2. Music Show Wins (20% Weight): M Countdown, Music Bank, Inkigayo. "
        "3. Global Fandom (Voting/Sales - 30% Weight): Mubeat, Idol Champ, Tenasia for voting. Hanteo and Circle Chart for sales. "
        "Apply a 'Heat' weighting system: give bonuses for 'Perfect All-Kill' (PAK) and Momentum (climbing +10 spots). "
        "Return the ranking as ONLY a valid JSON array of objects. "
        "Each object MUST have the following keys: "
        "'rank' (integer), 'artist' (string), 'track' (string), "
        "'primary_metric_support' (string, e.g. 'Perfect All-Kill (PAK); 4-crown music show sweep'), "
        "and 'trend' (string: '+X Position', '-X Position', or 'Stable'). "
        "Do not include any other text, markdown formatting, or explanations outside the JSON array."
    )
    
    try:
        raw_response = _chat(prompt, system="You are an expert K-Pop music industry analyst and data synthesizer.")
        
        # Extract the JSON array from the response safely
        start_idx = raw_response.find('[')
        end_idx = raw_response.rfind(']') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = raw_response[start_idx:end_idx]
            try:
                ranking_data = json.loads(json_str)
                return JsonResponse({'ranking': ranking_data})
            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e}")
                print(f"Raw string used for parsing: {json_str}")
                return JsonResponse({'error': f'Invalid JSON: {str(e)}', 'raw': raw_response}, status=500)
        else:
            print(f"Failed to find JSON brackets in: {raw_response}")
            return JsonResponse({'error': 'Failed to parse JSON array from AI response.', 'raw': raw_response}, status=500)
            
    except Exception as e:
        print(f"Exception in ai_generate_ranking: {e}")
        return JsonResponse({'error': str(e)}, status=500)



def comeback_timeline(request):
    import calendar as py_calendar

    now = timezone.now()
    today_str = now.strftime('%Y-%m-%d')

    # Allow month navigation via query params
    try:
        nav_year = int(request.GET.get('year', now.year))
        nav_month = int(request.GET.get('month', now.month))
    except (ValueError, TypeError):
        nav_year, nav_month = now.year, now.month

    # Clamp to reasonable range
    if nav_month < 1 or nav_month > 12:
        nav_month = now.month
    if nav_year < 2020 or nav_year > 2030:
        nav_year = now.year

    # Previous / next month for nav links
    if nav_month == 1:
        prev_year, prev_month = nav_year - 1, 12
    else:
        prev_year, prev_month = nav_year, nav_month - 1
    if nav_month == 12:
        next_year, next_month = nav_year + 1, 1
    else:
        next_year, next_month = nav_year, nav_month + 1

    # â”€â”€ Build calendar grid â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    first_weekday, num_days = py_calendar.monthrange(nav_year, nav_month)
    empty_cells = (first_weekday + 1) % 7  # Sunday-start

    data_obj = ComebackData.objects.filter(
        year=nav_year, month=nav_month
    ).first()
    cal_data = data_obj.data if data_obj else {}

    days = []
    for _ in range(empty_cells):
        days.append({'empty': True})

    for d in range(1, num_days + 1):
        day_key = f"{nav_year}-{nav_month:02d}-{d:02d}"
        dd = cal_data.get(day_key, {})
        days.append({
            'num': d,
            'empty': False,
            'releases': dd.get('releases', []),
            'birthdays': dd.get('birthdays', []),
            'anniversaries': dd.get('anniversaries', []),
            'is_today': (
                nav_year == now.year
                and nav_month == now.month
                and d == now.day
            ),
            'is_past': day_key < today_str,
        })

    # â”€â”€ Build upcoming timeline (current + next 2 months) â”€â”€
    months_to_check = []
    for offset in range(3):
        m = nav_month + offset
        y = nav_year
        while m > 12:
            m -= 12
            y += 1
        months_to_check.append((y, m))

    all_releases = []
    for y, m in months_to_check:
        cb = ComebackData.objects.filter(year=y, month=m).first()
        if not cb:
            continue
        for date_key, details in cb.data.items():
            for r in details.get('releases', []):
                release_item = dict(r)
                release_item['date_str'] = date_key
                release_item['iso_date'] = f"{date_key}T09:00:00Z"
                all_releases.append(release_item)

    all_releases.sort(key=lambda x: x['date_str'])
    upcoming = [r for r in all_releases if r['date_str'] >= today_str]
    recent = sorted(
        [r for r in all_releases if r['date_str'] < today_str],
        key=lambda x: x['date_str'],
        reverse=True,
    )[:6]

    for release in upcoming:
        release['image'] = _optimize_home_image_url(release.get('image'), width=192, height=192)
    for release in recent:
        release['image'] = _optimize_home_image_url(release.get('image'), width=192, height=192)

    # Stats
    total_upcoming = len(upcoming)
    types_count = {}
    for r in upcoming:
        t = r.get('type', 'Release')
        types_count[t] = types_count.get(t, 0) + 1

    month_label = py_calendar.month_name[nav_month]

    return render(request, 'core/comebacks.html', {
        'days': days,
        'month_label': month_label,
        'nav_year': nav_year,
        'nav_month': nav_month,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'upcoming': upcoming[:20],
        'recent': recent,
        'total_upcoming': total_upcoming,
        'types_count': types_count,
    })


def calendar(request):
    import calendar as py_calendar
    now = timezone.now()
    year = now.year
    month = now.month
    
    # Get the days in month and starting weekday
    # py_calendar.monthrange returns (weekday of first day, number of days in month)
    # weekday: 0=Monday, 6=Sunday
    first_weekday, num_days = py_calendar.monthrange(year, month)
    
    # K-Sync calendar starts on Sunday (as per day labels in template)
    # If first_weekday is 0 (Mon), we need 1 empty cell (Sun).
    # If first_weekday is 6 (Sun), we need 0 empty cells.
    # Formula for Sunday-start: (first_weekday + 1) % 7
    empty_cells = (first_weekday + 1) % 7
    
    days = []
    # Add empty placeholders
    for _ in range(empty_cells):
        days.append({'empty': True})
    
    # Get actual data for this month
    data_obj = ComebackData.objects.filter(year=year, month=month).first()
    calendar_data = data_obj.data if data_obj else {}

    # Add actual days
    for day_num in range(1, num_days + 1):
        day_key = f"{year}-{month:02d}-{day_num:02d}"
        day_data = calendar_data.get(day_key, {})
        days.append({
            'num': day_num,
            'empty': False,
            'releases': day_data.get('releases', []),
            'birthdays': day_data.get('birthdays', []),
            'anniversaries': day_data.get('anniversaries', []),
            'is_today': (day_num == now.day)
        })

    context = {
        'days': days,
        'current_month': now.strftime('%B'),
        'current_year': year,
    }
    return render(request, 'core/calendar.html', context)


def idol_page(request, slug):
    from django.shortcuts import get_object_or_404
    import urllib.request
    import urllib.parse
    import logging
    logger = logging.getLogger(__name__)

    group = get_object_or_404(KPopGroup, slug=slug)
    _apply_stream_image_to_field(group, 'image_url')

    # Default accent colors per group type
    accent_map = {
        'GIRL': '#FF8EAF',
        'BOY': '#00f0ff',
        'SOLO': '#c084fc',
    }
    accent_rgb_map = {
        'GIRL': '255,142,175',
        'BOY': '0,240,255',
        'SOLO': '192,132,252',
    }

    # Get 3 related groups of the same type
    related = list(KPopGroup.objects.filter(group_type=group.group_type).exclude(pk=group.pk).order_by('rank')[:3])
    for related_group in related:
        _apply_stream_image_to_field(related_group, 'image_url')

    # Pull real releases, birthdays, and anniversaries from ComebackData
    now = timezone.now()
    months = [
        (now.year, now.month),
        (now.year if now.month < 12 else now.year + 1, now.month + 1 if now.month < 12 else 1),
    ]
    today_str = now.strftime('%Y-%m-%d')
    name_lower = group.name.lower()

    comeback_albums = []
    events = []
    for y, m in months:
        data_obj = ComebackData.objects.filter(year=y, month=m).first()
        if not data_obj:
            continue
        for date_key, day_data in data_obj.data.items():
            for r in day_data.get('releases', []):
                if name_lower in r.get('artist', '').lower():
                    comeback_albums.append({
                        'title': r.get('title', ''),
                        'image': _build_stream_image_url(r.get('image', '')),
                        'type': r.get('type', 'Release'),
                        'date_str': date_key,
                    })
                    if date_key >= today_str:
                        events.append({
                            'type': 'Release',
                            'title': r.get('title', 'New Release'),
                            'date': date_key,
                            'iso_date': f"{date_key}T09:00:00Z",
                        })
            for b in day_data.get('birthdays', []):
                if name_lower in (b.get('group', '') or '').lower() or name_lower in (b.get('name', '') or '').lower():
                    events.append({
                        'type': 'Birthday',
                        'title': f"{b.get('name', 'Member')} Birthday",
                        'date': date_key,
                        'iso_date': f"{date_key}T00:00:00Z" if date_key >= today_str else '',
                    })
            for a in day_data.get('anniversaries', []):
                if name_lower in (a.get('group', '') or '').lower():
                    events.append({
                        'type': 'Anniversary',
                        'title': f"{group.name} Debut Anniversary",
                        'date': date_key,
                        'iso_date': f"{date_key}T00:00:00Z" if date_key >= today_str else '',
                    })

    comeback_albums.sort(key=lambda x: x['date_str'], reverse=True)
    events.sort(key=lambda x: x['date'])

    # Pull charted tracks if this group appears in the daily ranking
    chart_tracks = []
    daily_rank = Ranking.objects.filter(timeframe='daily').first()
    if daily_rank and daily_rank.ranking_data:
        for item in daily_rank.ranking_data:
            if name_lower in item.get('artist', '').lower():
                chart_tracks.append({
                    'title': item.get('track', ''),
                    'image': _build_stream_image_url(item.get('artwork_url', '')),
                    'album': item.get('album', ''),
                })

    # â”€â”€ iTunes: Fetch discography + top songs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    itunes_albums = []
    itunes_tracks = []

    # Map group names to iTunes search terms where needed
    ITUNES_NAME_MAP = {
        '(G)I-DLE': 'G I-DLE',
    }
    itunes_term = ITUNES_NAME_MAP.get(group.name, group.name)
    encoded_term = urllib.parse.quote_plus(itunes_term)

    def _itunes_fetch(entity, limit):
        url = (
            f"https://itunes.apple.com/search?term={encoded_term}"
            f"&entity={entity}&attribute=artistTerm&limit={limit}"
        )
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                return json.loads(resp.read().decode()).get('results', [])
        except Exception as e:
            logger.warning("iTunes %s fetch failed for %s: %s", entity, group.name, e)
            return []

    # Fetch albums (up to 20)
    for item in _itunes_fetch('album', 20):
        art = item.get('artworkUrl100', '').replace('100x100bb', '600x600bb')
        itunes_albums.append({
            'title': item.get('collectionName', ''),
            'image': art,
            'type': item.get('collectionType', 'Album'),
            'date_str': (item.get('releaseDate', '') or '')[:10],
            'track_count': item.get('trackCount', 0),
            'collection_id': item.get('collectionId', ''),
            'itunes_url': item.get('collectionViewUrl', ''),
        })
    itunes_albums.sort(key=lambda x: x['date_str'], reverse=True)

    # Fetch top songs (up to 15)
    for item in _itunes_fetch('song', 15):
        art = item.get('artworkUrl100', '').replace('100x100bb', '600x600bb')
        duration_ms = item.get('trackTimeMillis', 0) or 0
        mins, secs = divmod(duration_ms // 1000, 60)
        itunes_tracks.append({
            'title': item.get('trackName', ''),
            'album': item.get('collectionName', ''),
            'image': art,
            'preview_url': item.get('previewUrl', ''),
            'duration': f"{mins}:{secs:02d}",
            'itunes_url': item.get('trackViewUrl', ''),
        })

    # Merge: Use iTunes albums as primary, fall back to comeback data
    albums = itunes_albums if itunes_albums else comeback_albums
    tracks = itunes_tracks if itunes_tracks else chart_tracks

    context = {
        'group': group,
        'accent_color': accent_map.get(group.group_type, '#FF8EAF'),
        'accent_rgb': accent_rgb_map.get(group.group_type, '255,142,175'),
        'related_groups': related,
        'description': group.description or f"Explore the world of {group.name} - members, discography, top tracks, and more.",
        'members': [
            {
                'name': m.stage_name or m.name,
                'full_name': m.name,
                'position': m.position,
                'image': m.image_url or '',
            }
            for m in group.members.all()
        ],
        'albums': albums,
        'tracks': tracks,
        'events': events,
        'gallery': [],
    }
    return render(request, 'core/idol_band_page.html', context)


def album_detail(request, slug, collection_id):
    """Album detail page - fetches tracklist from iTunes."""
    from django.shortcuts import get_object_or_404
    import urllib.request
    import urllib.parse
    import logging
    logger = logging.getLogger(__name__)

    group = get_object_or_404(KPopGroup, slug=slug)

    accent_map = {
        'GIRL': '#FF8EAF',
        'BOY': '#00f0ff',
        'SOLO': '#c084fc',
    }
    accent_rgb_map = {
        'GIRL': '255,142,175',
        'BOY': '0,240,255',
        'SOLO': '192,132,252',
    }

    # Lookup album + tracks from iTunes
    url = (
        f"https://itunes.apple.com/lookup"
        f"?id={urllib.parse.quote_plus(str(collection_id))}&entity=song"
    )
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0'}
    )
    album_info = {}
    tracks = []
    response_status = None
    response_body = ''
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            response_status = getattr(resp, 'status', resp.getcode())
            response_body = resp.read().decode()

        if response_status != 200:
            raise ValueError(f"Non-200 iTunes response: {response_status}")

        data = json.loads(response_body)
        results = data.get('results')
        if not isinstance(results, list) or not results:
            raise ValueError("Missing or empty iTunes results")

        for item in results:
            wt = item.get('wrapperType', '')
            if wt == 'collection':
                art = item.get(
                    'artworkUrl100', ''
                ).replace('100x100bb', '1200x1200bb')
                album_info = {
                    'title': item.get('collectionName', ''),
                    'artist': item.get('artistName', ''),
                    'image': art,
                    'release_date': (
                        item.get('releaseDate', '') or ''
                    )[:10],
                    'track_count': item.get('trackCount', 0),
                    'genre': item.get('primaryGenreName', ''),
                    'copyright': item.get('copyright', ''),
                    'itunes_url': item.get(
                        'collectionViewUrl', ''
                    ),
                }
            elif wt == 'track':
                dur_ms = item.get('trackTimeMillis', 0) or 0
                mins, secs = divmod(dur_ms // 1000, 60)
                tracks.append({
                    'number': item.get('trackNumber', 0),
                    'title': item.get('trackName', ''),
                    'duration': f"{mins}:{secs:02d}",
                    'duration_ms': dur_ms,
                    'preview_url': item.get('previewUrl', ''),
                    'image': item.get(
                        'artworkUrl100', ''
                    ).replace('100x100bb', '600x600bb'),
                })

        if not album_info:
            raise ValueError("Missing collection metadata in iTunes results")
    except Exception as e:
        logger.warning(
            (
                "iTunes album lookup failed for collection_id=%s "
                "status=%s error=%s response_preview=%r"
            ),
            collection_id,
            response_status,
            e,
            response_body[:200],
        )
        raise Http404("Album not found")

    tracks.sort(key=lambda x: x['number'])

    # Total album duration
    total_ms = sum(t['duration_ms'] for t in tracks)
    total_mins = total_ms // 60000

    context = {
        'group': group,
        'album': album_info,
        'tracks': tracks,
        'total_mins': total_mins,
        'accent_color': accent_map.get(group.group_type, '#FF8EAF'),
        'accent_rgb': accent_rgb_map.get(
            group.group_type, '255,142,175'
        ),
    }
    return render(request, 'core/album_detail.html', context)


@csrf_exempt
@require_POST
def vote_poll(request):
    from .models import LivePollOption
    try:
        data = json.loads(request.body)
        option_id = data.get('option_id')
        option = LivePollOption.objects.get(id=option_id)

        if _is_poll_early_access_locked(request, option.poll):
            return JsonResponse({
                'success': False,
                'error': 'Early access is available to premium fan-club tiers only right now.',
            }, status=403)

        option.votes += 1
        option.save()

        event_slug = str(data.get('event_slug') or '').strip()
        if event_slug and request.user.is_authenticated:
            event = LimitedTimeEvent.objects.filter(
                slug=event_slug,
                is_active=True,
                starts_at__lte=timezone.now(),
                ends_at__gte=timezone.now(),
            ).first()
            if event:
                participation, _ = EventParticipation.objects.get_or_create(
                    user=request.user,
                    event=event,
                )
                participation.votes_cast = int(participation.votes_cast or 0) + 1
                participation.save(update_fields=['votes_cast'])
        
        poll = option.poll
        total_votes = sum(o.votes for o in poll.options.all())
        
        results = {
            o.id: o.percentage() for o in poll.options.all()
        }
        
        return JsonResponse({'success': True, 'total_votes': total_votes, 'results': results})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
#  STAFF-ONLY CONTEST MANAGEMENT API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _staff_required(request):
    """Return a 403 JsonResponse if the user is not staff, else None."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({'error': 'Forbidden'}, status=403)
    return None


@require_POST
@login_required
def api_contest_create(request):
    denied = _staff_required(request)
    if denied:
        return denied
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    title = bleach.clean(data.get('title', '').strip(), tags=[], strip=True)
    slug = bleach.clean(data.get('slug', '').strip(), tags=[], strip=True)
    if not title or not slug:
        return JsonResponse({'error': 'title and slug are required'}, status=400)
    if Contest.objects.filter(slug=slug).exists():
        return JsonResponse({'error': 'A contest with that slug already exists'}, status=400)

    contest = Contest.objects.create(
        title=title,
        slug=slug,
        subtitle=bleach.clean(data.get('subtitle', ''), tags=[], strip=True),
        description=bleach.clean(data.get('description', ''), tags=[], strip=True),
        image=bleach.clean(data.get('image', ''), tags=[], strip=True),
        artist=bleach.clean(data.get('artist', ''), tags=[], strip=True),
        prizes=data.get('prizes', []),
        rules=bleach.clean(data.get('rules', ''), tags=[], strip=True),
        entry_question=bleach.clean(data.get('entry_question', ''), tags=[], strip=True),
        deadline=data.get('deadline'),
        is_active=bool(data.get('is_active', True)),
        is_featured=bool(data.get('is_featured', False)),
        contest_number=bleach.clean(data.get('contest_number', ''), tags=[], strip=True),
    )
    return JsonResponse({'success': True, 'id': contest.pk, 'slug': contest.slug})


@require_POST
@login_required
def api_contest_edit(request, contest_id):
    denied = _staff_required(request)
    if denied:
        return denied
    contest = get_object_or_404(Contest, pk=contest_id)
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if 'title' in data:
        contest.title = bleach.clean(data['title'], tags=[], strip=True)
    if 'subtitle' in data:
        contest.subtitle = bleach.clean(data['subtitle'], tags=[], strip=True)
    if 'description' in data:
        contest.description = bleach.clean(data['description'], tags=[], strip=True)
    if 'image' in data:
        contest.image = bleach.clean(data['image'], tags=[], strip=True)
    if 'artist' in data:
        contest.artist = bleach.clean(data['artist'], tags=[], strip=True)
    if 'prizes' in data:
        contest.prizes = data['prizes']
    if 'rules' in data:
        contest.rules = bleach.clean(data['rules'], tags=[], strip=True)
    if 'entry_question' in data:
        contest.entry_question = bleach.clean(data['entry_question'], tags=[], strip=True)
    if 'deadline' in data:
        contest.deadline = data['deadline']
    if 'is_active' in data:
        contest.is_active = bool(data['is_active'])
    if 'is_featured' in data:
        contest.is_featured = bool(data['is_featured'])
    if 'contest_number' in data:
        contest.contest_number = bleach.clean(data['contest_number'], tags=[], strip=True)
    contest.save()
    return JsonResponse({'success': True})


@require_POST
@login_required
def api_contest_toggle(request, contest_id):
    denied = _staff_required(request)
    if denied:
        return denied
    contest = get_object_or_404(Contest, pk=contest_id)
    field = request.POST.get('field', 'is_active')
    if field not in ('is_active', 'is_featured'):
        return JsonResponse({'error': 'Invalid field'}, status=400)
    setattr(contest, field, not getattr(contest, field))
    contest.save(update_fields=[field])
    return JsonResponse({'success': True, 'value': getattr(contest, field)})


@require_POST
@login_required
def api_contest_delete(request, contest_id):
    denied = _staff_required(request)
    if denied:
        return denied
    contest = get_object_or_404(Contest, pk=contest_id)
    contest.delete()
    return JsonResponse({'success': True})


def fan_clubs(request):
    groups = KPopGroup.objects.prefetch_related(
        'members'
    ).order_by('rank', 'name')
    total_members = FanClubMembership.objects.count()
    active_events = LimitedTimeEvent.objects.filter(
        is_active=True,
        starts_at__lte=timezone.now(),
        ends_at__gte=timezone.now(),
    ).count()
    joined_ids = set()
    if request.user.is_authenticated:
        joined_ids = set(
            FanClubMembership.objects.filter(
                user=request.user
            ).values_list('group_id', flat=True)
        )
    launches = ClubLaunch.objects.all()[:10]
    return render(request, 'core/fan_clubs.html', {
        'fan_clubs': groups,
        'total_clubs': groups.count(),
        'total_members': total_members,
        'active_events': active_events,
        'joined_ids': joined_ids,
        'launches': launches
    })


@login_required
def start_club_view(request):
    if request.method == 'POST':
        club_name = request.POST.get('club_name', 'New Club')
        artist = request.POST.get('target_artist', 'Unknown Artist')
        archetype = request.POST.get('archetype', 'vanguard')
        mission_statement = request.POST.get('mission_statement', '')
        founders_raw = request.POST.get('founders', '[]')
        
        try:
            founders_list = json.loads(founders_raw)
        except:
            founders_list = []

        # Create Club Launch Record for the Hype Ticker
        ClubLaunch.objects.create(
            name=club_name,
            artist=artist,
            mission_statement=mission_statement,
            archetype=archetype,
            creator=request.user
        )

        # Award Genesis Badge to Creator
        UserBadge.objects.get_or_create(
            user=request.user,
            name=f"Genesis - {club_name}",
            badge_type='GENESIS'
        )
            
        # Create Real Invitations and Notifications
        for identifier in founders_list:
            # Try to find by username first, then email
            user = User.objects.filter(models.Q(username__iexact=identifier) | models.Q(email__iexact=identifier)).first()
            
            # Create Invitation Record
            invitation = ClubInvitation.objects.create(
                sender=request.user,
                invitee=user,
                invitee_email=identifier if not user else None,
                club_name=club_name,
                archetype=archetype
            )
            
            # Create Notification if user exists
            if user:
                UserNotification.objects.create(
                    user=user,
                    message=f"You've been invited by {request.user.username} to join the Launch Team for {club_name}!",
                    type='INVITE',
                    link=f"/fan-clubs/invitation/{invitation.id}/" # Placeholder link
                )
            
        # Success state
        return render(request, 'core/start_club.html', {
            'status': 'success',
            'archetype': archetype,
            'founders_count': len(founders_list)
        })
    return render(request, 'core/start_club.html')

@login_required
def get_notifications(request):
    notifications = UserNotification.objects.filter(user=request.user, is_read=False)[:5]
    data = [{
        'id': n.id,
        'message': n.message,
        'type': n.type,
        'created_at': n.created_at.strftime("%b %d, %H:%M"),
        'link': n.link
    } for n in notifications]
    
    return JsonResponse({
        'status': 'success',
        'notifications': data,
        'unread_count': UserNotification.objects.filter(user=request.user, is_read=False).count()
    })

@login_required
@require_POST
def mark_notification_read(request, notification_id):
    try:
        notification = UserNotification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    except UserNotification.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)


@require_POST
@login_required
def api_fan_club_join(request):
    try:
        data = json.loads(request.body)
        group_id = int(data.get('group_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid data'}, status=400)
    group = get_object_or_404(KPopGroup, pk=group_id)
    membership, created = FanClubMembership.objects.get_or_create(
        user=request.user, group=group,
    )
    
    # Award Genesis Badge if among first 5
    if created:
        count = group.fan_club_members.count()
        if count <= 5:
            membership.is_genesis = True
            membership.save()
            UserBadge.objects.get_or_create(
                user=request.user,
                name=f"Genesis - {group.name}",
                badge_type='GENESIS',
                group=group
            )

    count = group.fan_club_members.count()
    return JsonResponse({
        'success': True,
        'joined': True,
        'created': created,
        'member_count': count,
        'group_name': group.name,
    })


@require_POST
@login_required
def api_fan_club_leave(request):
    try:
        data = json.loads(request.body)
        group_id = int(data.get('group_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Invalid data'}, status=400)
    group = get_object_or_404(KPopGroup, pk=group_id)
    deleted, _ = FanClubMembership.objects.filter(
        user=request.user, group=group,
    ).delete()
    count = group.fan_club_members.count()
    return JsonResponse({
        'success': True,
        'joined': False,
        'member_count': count,
    })


@login_required
@require_http_methods(["GET"])
def api_fan_club_perks(request):
    group_id = request.GET.get('group_id')
    if not group_id:
        return JsonResponse({'error': 'group_id is required'}, status=400)
    try:
        group_id = int(group_id)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid group_id'}, status=400)

    membership = FanClubMembership.objects.filter(user=request.user, group_id=group_id).first()
    if not membership:
        return JsonResponse({
            'success': True,
            'joined': False,
            'tier': 'FREE',
            'perks': {
                'early_access_polls': False,
                'premium_themes': False,
                'exclusive_voice_dj_packs': False,
            },
            'voice_dj_pack_access': [],
        })

    tier = str(membership.tier or 'FREE').upper()
    pack_access = []
    if tier == 'PLUS':
        pack_access = ['plus-future-bass', 'plus-midnight-glow']
    elif tier == 'ULTRA':
        pack_access = ['plus-future-bass', 'plus-midnight-glow', 'ultra-neon-arena', 'ultra-afterparty-hype']

    return JsonResponse({
        'success': True,
        'joined': True,
        'group_id': group_id,
        'tier': tier,
        'perks': membership.perks,
        'voice_dj_pack_access': pack_access,
    })


@require_POST
@login_required
def api_fan_club_set_tier(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    try:
        group_id = int(data.get('group_id', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid group_id'}, status=400)

    tier = str(data.get('tier') or '').strip().upper()
    if tier not in TIER_RANK:
        return JsonResponse({'error': 'Invalid tier'}, status=400)

    membership = FanClubMembership.objects.filter(user=request.user, group_id=group_id).first()
    if not membership:
        return JsonResponse({'error': 'Join the fan club before setting a tier'}, status=400)

    membership.tier = tier
    membership.save(update_fields=['tier'])

    return JsonResponse({
        'success': True,
        'group_id': group_id,
        'tier': membership.tier,
        'perks': membership.perks,
    })


@require_http_methods(["GET"])
def api_monthly_events(request):
    now = timezone.now()
    events = LimitedTimeEvent.objects.filter(
        is_active=True,
        starts_at__lte=now,
        ends_at__gte=now,
    ).order_by('starts_at')

    payload = []
    for event in events:
        badge_drops = list(
            event.badge_drops.filter(is_active=True)
            .order_by('-created_at')
            .values('id', 'badge_name', 'rarity', 'minimum_tier', 'min_votes_required')
        )
        primary_badge_drop = badge_drops[0] if badge_drops else None
        payload.append({
            'id': event.id,
            'slug': event.slug,
            'title': event.title,
            'event_type': event.event_type,
            'description': event.description,
            'starts_at': event.starts_at.isoformat(),
            'ends_at': event.ends_at.isoformat(),
            'badge_drop_count': len(badge_drops),
            'primary_badge_drop': primary_badge_drop,
        })

    return JsonResponse({'success': True, 'events': payload})


@require_POST
@login_required
def api_event_join(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    event_id = data.get('event_id')
    event_slug = str(data.get('event_slug') or '').strip()
    event = None
    if event_id:
        try:
            event = LimitedTimeEvent.objects.filter(pk=int(event_id)).first()
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid event_id'}, status=400)
    elif event_slug:
        event = LimitedTimeEvent.objects.filter(slug=event_slug).first()

    if not event:
        return JsonResponse({'error': 'Event not found'}, status=404)
    if not event.is_active or timezone.now() < event.starts_at or timezone.now() > event.ends_at:
        return JsonResponse({'error': 'Event is not currently active'}, status=400)

    participation, created = EventParticipation.objects.get_or_create(
        user=request.user,
        event=event,
    )
    return JsonResponse({
        'success': True,
        'joined': True,
        'created': created,
        'event_id': event.id,
        'event_slug': event.slug,
        'votes_cast': participation.votes_cast,
    })


@require_POST
@login_required
def api_event_claim_badge(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)

    try:
        badge_drop_id = int(data.get('badge_drop_id', 0))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid badge_drop_id'}, status=400)

    badge_drop = EventBadgeDrop.objects.select_related('event').filter(pk=badge_drop_id, is_active=True).first()
    if not badge_drop:
        return JsonResponse({'error': 'Badge drop not found'}, status=404)

    event = badge_drop.event
    now = timezone.now()
    if not event.is_active or now < event.starts_at or now > event.ends_at:
        return JsonResponse({'error': 'Badge drop event is not active'}, status=400)

    participation = EventParticipation.objects.filter(user=request.user, event=event).first()
    votes_cast = int(participation.votes_cast or 0) if participation else 0
    if votes_cast < int(badge_drop.min_votes_required or 0):
        return JsonResponse({
            'error': 'Not enough participation yet',
            'votes_cast': votes_cast,
            'min_votes_required': badge_drop.min_votes_required,
        }, status=400)

    membership = FanClubMembership.objects.filter(user=request.user).order_by('-joined_at').first()
    user_tier = str(membership.tier if membership else 'FREE').upper()
    if not _tier_meets_requirement(user_tier, badge_drop.minimum_tier):
        return JsonResponse({
            'error': 'Tier upgrade required for this badge drop',
            'required_tier': badge_drop.minimum_tier,
            'your_tier': user_tier,
        }, status=403)

    badge, created = UserBadge.objects.get_or_create(
        user=request.user,
        name=badge_drop.badge_name,
        defaults={
            'badge_type': badge_drop.badge_type,
            'is_glowing': badge_drop.rarity in {'EPIC', 'LEGENDARY'},
        },
    )
    if not created:
        return JsonResponse({'success': True, 'claimed': False, 'already_owned': True, 'badge': badge.name})

    return JsonResponse({
        'success': True,
        'claimed': True,
        'badge': badge.name,
        'rarity': badge_drop.rarity,
    })

@csrf_exempt
@require_POST
def polish_mission_statement(request):
    """
    Use DeepSeek to turn a basic club description into a brutalist, 
    high-energy, cinematic K-Pop mission statement.
    """
    try:
        data = json.loads(request.body)
        raw_description = data.get('description', '').strip()
        
        if not raw_description:
            return JsonResponse({'error': 'Description is required'}, status=400)

        system_prompt = (
            "You are a premium K-Pop creative director. "
            "Your task is to rewrite a fan club description into a cinematic, high-energy, "
            "brutalist mission statement. Use punchy, evocative language. "
            "Avoid generic marketing fluff. Make it sound like a call to action for a global fandom. "
            "CRITICAL: Keep it strictly under 250 characters. "
            "Output ONLY the refined text."
        )
        
        refined_text = _chat(raw_description, system=system_prompt)
        
        return JsonResponse({'refined_text': refined_text})
        
    except Exception as e:
        logger.error("AI Brutalizer error: %s", e)
        return JsonResponse({'error': str(e)}, status=500)

def get_artist_stats(request):
    """
    Retrieves real-time statistics for a specific artist/group.
    Used for the 'Power Pulse' feature on the Start A Club page.
    """
    artist_name = request.GET.get('artist', '').strip()
    if not artist_name:
        return JsonResponse({'error': 'Artist name required'}, status=400)
    
    # 1. Try to find the group
    group = KPopGroup.objects.filter(name__icontains=artist_name).first()
    
    # 2. Count news articles (BlogArticles) mentioning the artist
    # We search the title and subtitle for the name
    news_count = BlogArticle.objects.filter(
        models.Q(title__icontains=artist_name) | 
        models.Q(subtitle__icontains=artist_name)
    ).count()
    
    # 3. Calculate reach potential (Fan club members or a random 'momentum' factor)
    reach = 0
    rank = "N/A"
    
    if group:
        rank = f"#{group.rank}" if group.rank else "Unranked"
        # Reach potential = current members + a "fandom gravity" multiplier
        base_fans = group.fan_club_members.count()
        reach = base_fans * 1.5 + 500  # Example logic: current fans + projected growth
    else:
        # Fallback for groups not in our DB yet
        reach = 1000  # Default starter potential
        
    return JsonResponse({
        'artist': artist_name,
        'rank': rank,
        'news_count': news_count,
        'reach_potential': int(reach),
        'found': group is not None
    })

def placeholder(request):
    return render(request, 'core/placeholder.html')


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


def cookie_policy(request):
    return render(request, 'core/cookie_policy.html')


def terms_of_service(request):
    return render(request, 'core/terms_of_service.html')

