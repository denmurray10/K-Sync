import json
import logging
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
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
    GameScore, SongRequest, Contest, ContestEntry,
    FanClubMembership, UserNotification, ClubInvitation, ClubLaunch, UserBadge,
    RadioTrack, RadioStationState, RadioPlaylist, RadioPlaylistTrack, RadioSchedule,
)

def _staff_only_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Authentication required'}, status=403)
    if not request.user.is_staff:
        return JsonResponse({'ok': False, 'error': 'Staff access required'}, status=403)
    return None

def api_schedule_data(request):
    """Returns the weekly schedule grouped by day for the frontend."""
    staff_check = _staff_only_json(request)
    if staff_check:
        return staff_check
    schedules = RadioSchedule.objects.select_related('playlist').all()
    
    # Initialize days
    day_map = {
        'MON': [], 'TUE': [], 'WED': [], 'THU': [], 
        'FRI': [], 'SAT': [], 'SUN': []
    }
    
    for s in schedules:
        day_map[s.day].append({
            'id': s.id,
            'time': s.start_time.strftime('%H:%M'),
            'duration': f"Until {s.end_time.strftime('%H:%M')}",
            'name': s.playlist.name,
            'playlist_id': s.playlist.id,
            'host': s.host,
            'description': s.description or s.playlist.description,
            'genre': s.genre,
            'icon': 'graphic_eq' if s.genre == 'LIVE' else 'album',
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
    if not request.user.is_staff:
        return redirect('signups_login')
    playlists = RadioPlaylist.objects.all()
    return render(request, 'core/playlist_manager.html', {'playlists': playlists})

def api_b2_tracks(request):
    """Lists files from Backblaze B2 bucket."""
    staff_check = _staff_only_json(request)
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
        for radio_track in RadioTrack.objects.all().only('title', 'artist', 'album_art', 'audio_url', 'duration', 'duration_seconds'):
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
                'url': download_url,
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
    staff_check = _staff_only_json(request)
    if staff_check:
        return staff_check
    try:
        data = json.loads(request.body)
        playlist_id = data.get('id')
        name = data.get('name')
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
            playlist.save()
        else:
            playlist = RadioPlaylist.objects.create(name=name)
            
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
                order=idx
            )
            
        return JsonResponse({'ok': True, 'id': playlist.id})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def api_schedule_save(request):
    """Saves a schedule entry."""
    staff_check = _staff_only_json(request)
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
        host = data.get('host', 'Auto DJ')
        genre = data.get('genre', 'MUSIC')
        
        if not all([day, start_time, end_time, playlist_id]):
            return JsonResponse({'ok': False, 'error': 'Missing required fields'}, status=400)
            
        playlist = RadioPlaylist.objects.get(id=playlist_id)
        
        # Check for overlaps (simplified for now)
        RadioSchedule.objects.create(
            day=day,
            start_time=start_time,
            end_time=end_time,
            playlist=playlist,
            host=host,
            genre=genre
        )
        
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

def api_playlist_data(request, playlist_id):
    """Returns data for a specific playlist."""
    staff_check = _staff_only_json(request)
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
            })
            
        return JsonResponse({
            'ok': True,
            'playlist': {
                'id': playlist.id,
                'name': playlist.name,
                'tracks': track_list
            }
        })
    except RadioPlaylist.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Playlist not found'}, status=404)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def api_playlist_ai_generate(request):
    """Generates a playlist draft with DeepSeek from RadioTrack records."""
    staff_check = _staff_only_json(request)
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
        RadioTrack.objects
        .exclude(audio_url='')
        .exclude(audio_url__isnull=True)
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
def api_schedule_delete(request, schedule_id):
    """Deletes a schedule entry."""
    staff_check = _staff_only_json(request)
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

logger = logging.getLogger(__name__)

# ── DeepSeek client ──────────────────────────────────────────────────────────
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

# ── Page views ───────────────────────────────────────────────────────────────


def home(request):
    now = timezone.now()
    data_current = ComebackData.objects.filter(year=now.year, month=now.month).first()
    data_next = ComebackData.objects.filter(year=now.year if now.month < 12 else now.year + 1, 
                                            month=now.month + 1 if now.month < 12 else 1).first()
    
    all_releases = []
    if data_current:
        for date_key, details in data_current.data.items():
            if 'releases' in details:
                # date_key is '2026-03-27' based on the error
                resolved_date_str = date_key
                for r in details['releases']:
                    r['date_str'] = resolved_date_str
                    r['iso_date'] = f"{resolved_date_str}T09:00:00Z"
                    all_releases.append(r)
    
    if data_next:
        for date_key, details in data_next.data.items():
             if 'releases' in details:
                resolved_date_str = date_key
                for r in details['releases']:
                    r['date_str'] = resolved_date_str
                    r['iso_date'] = f"{resolved_date_str}T09:00:00Z"
                    all_releases.append(r)

    all_releases.sort(key=lambda x: x['date_str'])
    today_str = now.strftime('%Y-%m-%d')
    upcoming_all = [r for r in all_releases if r['date_str'] >= today_str][:20]
    upcoming = upcoming_all[:4]
    upcoming_ticker = upcoming_all[4:20]
    
    # Ensure ticker isn't empty if we have releases but not enough for a separate ticker
    if not upcoming_ticker and upcoming:
        upcoming_ticker = upcoming

    # Trending Sidebar: Use daily ranking data (now synced from iChart)
    daily_rank = Ranking.objects.filter(timeframe='daily').first()
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
                if '+' in trend_raw or '▲' in trend_raw:
                    trend_icon = '▲'
                    trend_class = 'text-primary'
                    trend_value = ''.join(filter(str.isdigit, trend_raw))
                elif '-' in trend_raw or '▼' in trend_raw:
                    trend_icon = '▼'
                    trend_class = 'text-slate-500'
                    trend_value = ''.join(filter(str.isdigit, trend_raw))
                else:
                    trend_icon = '—'
                    trend_class = 'text-slate-500'
                    trend_value = ''
            else:
                # Flatline for no movement
                trend_icon = '—'
                trend_class = 'text-slate-500'
                trend_value = ''
            
            trending_all.append({
                'rank': idx + 1,
                'artist': item.get('artist'),
                'title': item.get('track'),
                'image': img_url,
                'trend_icon': trend_icon,
                'trend_class': trend_class,
                'trend_value': trend_value,
            })
            
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
                'trend_icon': '—',
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
                'trend_icon': '—',
                'trend_class': 'text-slate-500',
                'trend_value': '',
            })

    # Mock News Articles for Brutalist Section
    news_articles = BlogArticle.objects.order_by('-created_at')[:3]

    # Get the active LivePoll
    active_poll = LivePoll.objects.filter(is_active=True).first()
    
    return render(request, 'core/index.html', {
        'upcoming_comebacks': upcoming,
        'upcoming_ticker': upcoming_ticker,
        'trending_tracks': trending,
        'trending_ticker_tracks': trending_ticker,
        'news_articles': news_articles,
        'current_month': now.strftime('%B %Y'),
        'active_poll': active_poll
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
            if '+' in trend_raw or '▲' in trend_raw:
                trend_icon = '▲'
                trend_class = 'text-primary'
                trend_value = ''.join(filter(str.isdigit, trend_raw))
            elif '-' in trend_raw or '▼' in trend_raw:
                trend_icon = '▼'
                trend_class = 'text-slate-500'
                trend_value = ''.join(filter(str.isdigit, trend_raw))
            else:
                trend_icon = '—'
                trend_class = 'text-slate-500'
                trend_value = ''
        else:
            trend_icon = '—'
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

    groups = groups.order_by('rank')
    
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
    all_blog = BlogArticle.objects.order_by('-created_at')
    featured = all_blog.first()
    remaining = list(all_blog[1:]) if all_blog.count() > 1 else []

    cats = list(
        all_blog.order_by()
        .values_list('category', flat=True)
        .distinct()
    )

    return render(request, 'core/news.html', {
        'featured': featured,
        'articles': remaining,
        'all_articles': list(all_blog),
        'categories': cats,
        'total_count': all_blog.count(),
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

    # Keywords that indicate K-drama / general celebrity gossip — not K-pop
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

                # K-pop relevance filter — skip drama recaps and non-kpop content
                categories = [
                    c.text for c in item.findall('category') if c.text
                ]
                if not _is_kpop_article(title, categories):
                    logger.info("[RSS] Skipping non-kpop: %r", title)
                    continue

                # Cross-feed duplicate check — skip if very similar title already collected
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
                           " and São Paulo for the 2026 leg.",
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

def about_us(request):
    return render(request, 'core/about_us.html')

def coming_soon(request):
    return render(request, 'core/coming_soon.html')

def games(request):
    return render(request, 'core/games.html')

@csrf_exempt
@require_POST
def prelaunch_signup(request):
    import json
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
            return redirect('dashboard')
    return render(request, 'core/signup.html', {'error': error})


@login_required
def dashboard(request):
    now = timezone.now()
    today_str = now.strftime('%Y-%m-%d')
    user = request.user

    # Ensure profile exists
    profile, _ = UserProfile.objects.get_or_create(user=user)

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

    # Hot pick artists — top 20 most chosen as bias
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

    # Stats — mix platform + personal
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
        'badges': list(user.badges.all()),
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
        return JsonResponse({'ok': True})
    except (ValueError, KeyError, TypeError):
        return JsonResponse({'ok': False}, status=400)

def idol_scramble(request):
    names = []
    for g in KPopGroup.objects.all()[:60]:
        hint = f"{g.get_group_type_display()} · {g.label}"
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
    """Beat Streak v2 — same data pipeline, upgraded template."""
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

def bias_selector(request):
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
        "one name from the list — do not invent new names.\n\n"
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
            # Fallback — pick first in pool
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
            all_tracks = list(RadioTrack.objects.values_list('id', flat=True))
            if all_tracks:
                state.current_track_id = random.choice(all_tracks)
                state.started_at = end_time
            break

        # Emergency refill if queue low
        if len(state.up_next) < 3:
            all_tracks = list(RadioTrack.objects.values_list('id', flat=True))
            exclude_ids = set([state.current_track_id] + list(state.recently_played) + list(state.up_next))
            pool = [tid for tid in all_tracks if tid not in exclude_ids]
            if not pool: pool = [tid for tid in all_tracks if tid not in set(state.up_next)]
            if pool:
                random.shuffle(pool)
                state.up_next = (list(state.up_next) + pool[:5])[:5]

    state.save()
    return state

def live(request):
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=24)
    requested = SongRequest.objects.filter(
        created_at__gte=cutoff
    ).values_list('song_title', flat=True)
    requested_titles = [t.lower() for t in requested]

    # Fetch Radio Station State and Auto-Rotate if needed
    state = RadioStationState.objects.first()
    if state:
        state = _auto_rotate_station(state)

    current_track = None
    up_next_tracks = []
    recently_played_tracks = []

    if state:
        current_track = state.current_track

        # Fetch up_next tracks in order, limit to 6
        up_next_ids = (state.up_next or [])[:6]
        up_next_tracks = list(RadioTrack.objects.filter(id__in=up_next_ids))
        # Preserving order from list
        up_next_tracks.sort(key=lambda t: up_next_ids.index(t.id) if t.id in up_next_ids else 999)

        # Fetch recently_played tracks in order, limit to 6
        recent_ids = (state.recently_played or [])[:6]
        recently_played_tracks = list(RadioTrack.objects.filter(id__in=recent_ids))
        recently_played_tracks.sort(key=lambda t: recent_ids.index(t.id) if t.id in recent_ids else 999)

    # Calculate offset for synchronization
    current_offset = 0
    if state and state.started_at:
        elapsed = timezone.now() - state.started_at
        current_offset = max(0, int(elapsed.total_seconds()))

    return render(request, 'core/Live.html', {
        'requested_titles': requested_titles,
        'state': state,
        'current_track': current_track,
        'up_next_tracks': up_next_tracks,
        'recently_played_tracks': recently_played_tracks,
        'current_offset': current_offset,
    })

def api_live_rotate_track(request):
    """
    Rotates the radio station to the next track in the queue.
    """
    from core.models import RadioStationState, RadioTrack
    import random

    state = RadioStationState.objects.first()
    if not state:
        return JsonResponse({'ok': False, 'error': 'No station state found'}, status=404)

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
        all_tracks = list(RadioTrack.objects.values_list('id', flat=True))
        if all_tracks:
            state.current_track_id = random.choice(all_tracks)

    # Refill queue if low
    if len(state.up_next) < 3:
        all_tracks = list(RadioTrack.objects.values_list('id', flat=True))
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
    up_next_ids = state.up_next
    up_next_tracks = RadioTrack.objects.filter(id__in=up_next_ids)
    up_next_list = sorted(list(up_next_tracks), key=lambda t: up_next_ids.index(t.id))

    recently_played_ids = state.recently_played
    recently_played_tracks = RadioTrack.objects.filter(id__in=recently_played_ids)
    recently_played_list = sorted(list(recently_played_tracks), key=lambda t: recently_played_ids.index(t.id))

    return JsonResponse({
        'ok': True,
        'current_track': {
            'title': current.title,
            'artist': current.artist,
            'album_art': current.album_art,
            'audio_url': current.audio_url,
            'duration': current.duration,
        },
        'up_next': [
            {'title': t.title, 'artist': t.artist, 'album_art': t.album_art}
            for t in up_next_list[:6]
        ],
        'recently_played': [
            {'title': t.title, 'artist': t.artist, 'album_art': t.album_art}
            for t in recently_played_list[:6]
        ]
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
    articles = BlogArticle.objects.order_by('-created_at')[:30]
    cats = list(
        BlogArticle.objects.order_by()
        .values_list('category', flat=True)
        .distinct()
    )
    return render(request, 'core/blog_page.html', {
        'articles': articles,
        'categories': cats,
    })


def blog_article_read(request, slug):
    from django.shortcuts import get_object_or_404
    article = get_object_or_404(BlogArticle, slug=slug)
    related = (
        BlogArticle.objects
        .filter(category=article.category)
        .exclude(pk=article.pk)[:3]
    )
    return render(request, 'core/blog_article.html', {
        'article': article,
        'related': related,
    })


def _fetch_blog_image(title, category, excerpt='', variant=1):
    """Use DeepSeek for keywords, fetch via Serper, upload to Cloudinary."""
    import cloudinary
    import cloudinary.uploader
    serper_key = getattr(settings, 'SERPER_API_KEY', '')
    if not serper_key:
        return ''

    cloudinary.config(
        cloud_name=getattr(settings, 'CLOUDINARY_CLOUD_NAME', ''),
        api_key=getattr(settings, 'CLOUDINARY_API_KEY', ''),
        api_secret=getattr(settings, 'CLOUDINARY_API_SECRET', ''),
        secure=True,
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
                            "for %r: %s — trying next item",
                            variant, img_url, upload_err,
                        )
                        continue
        except Exception:
            pass
    return ''


def _do_blog_generate():
    """
    Core blog generation logic — fetch RSS articles and write new ones via AI.
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

        # ── DeepSeek Reasoner article ──
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
            f"1. Opening — hook the reader and introduce the story\n"
            f"2. Background — artist/group history and context\n"
            f"3. The News — detailed breakdown of the main story\n"
            f"4. Fan & Community Reaction — what fans are saying\n"
            f"5. Industry Analysis — impact and significance\n"
            f"6. What's Next — forward-looking conclusion\n\n"
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

        # ── Fetch image via Serper ──
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

        # Post to X (Twitter)
        try:
            _post_to_x(article)
        except Exception as e:
            logger.warning("[x] Post failed for %r: %s", title, e)

        # Post to Pinterest
        try:
            _post_to_pinterest(article)
        except Exception as e:
            logger.warning("[pinterest] Post failed for %r: %s", title, e)

        # Keep inter-linking list current for subsequent articles
        existing_articles.append({'slug': base_slug, 'title': title})

    logger.info("[blog] Auto-generate run complete — created %d article(s).", created)
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
        logger.debug("[facebook] No credentials configured — skipping scheduled post.")
        return

    if article.facebook_posted_at or article.facebook_post_id:
        logger.debug("[facebook] Already handled article %r — skipping.", article.slug)
        return

    # Default: schedule 1 hour from now
    if scheduled_unix_ts is None:
        scheduled_unix_ts = int(_time.time()) + 3600

    hook = _social_hook(article)
    plain_excerpt = _article_opening_excerpt(article, max_chars=400)
    hashtags = ' '.join(_social_hashtags('facebook', article))

    # Construct a more substantial message with hook and title first
    message = (
        f"{hook} {article.title}\n\n"
        f"{plain_excerpt}\n\n"
        "Link to the article in the comments\n\n"
        f"{hashtags}"
    )

    # Use the Page Photos endpoint to create a Photo Post.
    # This avoids the "link preview" box at the bottom (which would show cloudinary.com)
    # and makes the image the focus of the post.
    payload = {
        'caption': message,
        'url': article.image,
        'published': False,
        'scheduled_publish_time': scheduled_unix_ts,
    }

    try:
        resp = requests.post(
            f'https://graph.facebook.com/v22.0/{page_id}/photos',
            json=payload,
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
                "[facebook] Scheduled link post created for %r — post id: %s",
                article.title, result['id'],
            )
        else:
            logger.warning(
                "[facebook] Scheduled post failed for %r — %s",
                article.title, result,
            )
    except Exception as e:
        logger.warning("[facebook] Request error for %r: %s", article.title, e)


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
        logger.warning("[instagram] No image for %r — skipping.", article.title)
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
        logger.info("[instagram] Posted %r — id: %s", article.title, result['id'])
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

    text = _html.unescape(' '.join((raw or '').split())).strip()
    if not text:
        return ''
    if len(text) <= max_chars:
        return text

    cut = text[:max_chars]
    if ' ' in cut:
        cut = cut.rsplit(' ', 1)[0]
    return cut.rstrip('.,;:!') + '…'


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
        return "🎧 New review dropped"
    if cat.lower() == 'comeback':
        return "🚨 Comeback alert"
    return "🔥 New K-Pop update"


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
        trimmed = trimmed[:-2].rstrip() + '…' if len(trimmed) > 2 else ''

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
    api_key = getattr(settings, 'X_API_KEY', '')
    api_secret = getattr(settings, 'X_API_SECRET', '')
    access_token = getattr(settings, 'X_ACCESS_TOKEN', '')
    access_secret = getattr(settings, 'X_ACCESS_TOKEN_SECRET', '')
    if not all([api_key, api_secret, access_token, access_secret]):
        logger.debug("[x] Credentials not configured — skipping.")
        return

    if article.x_posted_at:
        logger.debug("[x] Already posted article %r — skipping.", article.slug)
        return

    article_url = _social_article_url(article, source='x')
    title = article.title[:200]
    hook = _social_hook(article)
    hashtags = ' '.join(_social_hashtags('x', article))

    title_text = f"{hook}: {title}"
    if len(title_text) > 110:
        title_text = title_text[:109].rstrip() + '…'

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
        logger.info("[x] Tweeted %r — id: %s", article.title, result['data']['id'])
    else:
        logger.warning("[x] Tweet failed: %s", result)


def _post_to_pinterest(article):
    """
    Creates a Pinterest Pin for the article.
    Requires PINTEREST_ACCESS_TOKEN and PINTEREST_BOARD_ID in settings.
    """
    access_token = getattr(settings, 'PINTEREST_ACCESS_TOKEN', '')
    board_id = getattr(settings, 'PINTEREST_BOARD_ID', '')
    if not access_token or not board_id:
        logger.debug("[pinterest] Credentials not configured — skipping.")
        return

    if article.pinterest_posted_at:
        logger.debug("[pinterest] Already posted article %r — skipping.", article.slug)
        return

    if not article.image:
        logger.warning("[pinterest] No image for %r — skipping.", article.title)
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
        logger.info("[pinterest] Pin created for %r — id: %s",
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
    from django.shortcuts import redirect

    all_articles = list(BlogArticle.objects.all())
    if len(all_articles) < 2:
        return redirect('news')

    # Build a lookup of title -> slug for all articles
    article_map = {a.title: a.slug for a in all_articles}

    updated = 0
    for article in all_articles:
        # Collect other articles as link candidates
        others = [
            {'title': t, 'slug': s}
            for t, s in article_map.items()
            if t != article.title
        ]
        if not others:
            continue

        candidates = '\n'.join(
            f'- "{o["title"]}" -> /blog/{o["slug"]}/'
            for o in others[:15]
        )

        prompt = (
            f"You are an SEO editor. Review the following HTML article and "
            f"add hyperlinks (<a href=\"URL\">anchor text</a>) ONLY where "
            f"the following article titles (or key subjects from them) are "
            f"*naturally mentioned* in the text. Do not force links — only "
            f"add them where they genuinely fit. Do NOT change any other "
            f"content, wording, or HTML structure.\n\n"
            f"Candidate links:\n{candidates}\n\n"
            f"Article HTML:\n{article.body_html}\n\n"
            f"Return ONLY the complete modified HTML with links added "
            f"(or unchanged if no natural fits were found). "
            f"No explanation, no markdown fences."
        )

        try:
            updated_html = _chat(
                prompt,
                system=(
                    "You are an expert SEO editor. You add internal hyperlinks "
                    "to HTML articles without changing any other content. "
                    "Return only the raw HTML."
                ),
            )
            # Sanity check: make sure we got HTML back
            if updated_html and '<p>' in updated_html:
                article.body_html = updated_html
                # Use update to skip bleach re-sanitization stripping new <a> tags
                BlogArticle.objects.filter(pk=article.pk).update(
                    body_html=updated_html
                )
                updated += 1
        except Exception:
            continue

    return redirect('news')


def new_release_spotlight(request):
    return render(request, 'core/new_release_spotlight.html')

def streaming_party_chat(request):
    return render(request, 'core/streaming_party_chat.html')

def confetti_rain(request):
    return render(request, 'core/confetti_rain.html')

# ── AI Endpoints ─────────────────────────────────────────────────────────────

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
            f"You are an enthusiastic K-Pop radio DJ. Write a punchy 1–2 sentence "
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
            f"Return ONLY valid JSON in this exact format — no markdown, no explanation: "
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

    # ── Build calendar grid ──────────────────────────────
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

    # ── Build upcoming timeline (current + next 2 months) ──
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
                r['date_str'] = date_key
                r['iso_date'] = f"{date_key}T09:00:00Z"
                all_releases.append(r)

    all_releases.sort(key=lambda x: x['date_str'])
    upcoming = [r for r in all_releases if r['date_str'] >= today_str]
    recent = sorted(
        [r for r in all_releases if r['date_str'] < today_str],
        key=lambda x: x['date_str'],
        reverse=True,
    )[:6]

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
    related = KPopGroup.objects.filter(group_type=group.group_type).exclude(pk=group.pk).order_by('rank')[:3]

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
                        'image': r.get('image', ''),
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
                    'image': item.get('artwork_url', ''),
                    'album': item.get('album', ''),
                })

    # ── iTunes: Fetch discography + top songs ────────────────────────────
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
        'description': group.description or f"Explore the world of {group.name} — members, discography, top tracks, and more.",
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
    """Album detail page — fetches tracklist from iTunes."""
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
        option.votes += 1
        option.save()
        
        poll = option.poll
        total_votes = sum(o.votes for o in poll.options.all())
        
        results = {
            o.id: o.percentage() for o in poll.options.all()
        }
        
        return JsonResponse({'success': True, 'total_votes': total_votes, 'results': results})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ────────────────────────────────────────────────────────────────────
#  STAFF-ONLY CONTEST MANAGEMENT API
# ────────────────────────────────────────────────────────────────────

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
