import json
from django.utils import timezone
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
import requests
from openai import OpenAI
from .models import Ranking, ComebackData, KPopGroup, LivePoll

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
        max_tokens=4000,
        temperature=0.8,
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
    news_articles = [
        {
            'category': 'Exclusive',
            'title': "BLACKPINK's Lisa Announces Global Fan-Meet Tour",
            'excerpt': "The 'Lalisa' star is set to hit 12 cities across Asia and Europe starting next month.",
            'date': 'Oct 24, 2025',
            'image': 'https://images.unsplash.com/photo-1514525253361-bee8a48740d0?auto=format&fit=crop&q=80&w=800'
        },
        {
            'category': 'Charts',
            'title': "Stray Kids 'ATE' Remains #1 on World Albums Chart",
            'excerpt': "The group continues their dominant streak on global charts for the 5th consecutive week.",
            'date': 'Oct 22, 2025',
            'image': 'https://images.unsplash.com/photo-1493225255756-d9584f8606e9?auto=format&fit=crop&q=80&w=800'
        },
        {
            'category': 'New Release',
            'title': "LE SSERAFIM Drops Teaser for Japan Debut Single",
            'excerpt': "Fearless as ever, the quintet prepares for a massive Japanese market expansion.",
            'date': 'Oct 20, 2025',
            'image': 'https://images.unsplash.com/photo-1526218626217-dc65a29bb444?auto=format&fit=crop&q=80&w=800'
        }
    ]

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

    groups = KPopGroup.objects.all().order_by('rank')
    return render(request, 'core/idols.html', {'today_events': today_events, 'groups': groups})


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

def news(request):
    return render(request, 'core/news.html')

def shop(request):
    return render(request, 'core/shop.html')

def about_us(request):
    return render(request, 'core/about_us.html')

def achievement_popup(request):
    return render(request, 'core/achievement_popup.html')

def login_page(request):
    return render(request, 'core/login.html')

def promo(request):
    return render(request, 'core/promo.html')

def signup(request):
    return render(request, 'core/signup.html')

def request_track(request):
    return render(request, 'core/request_track.html')

def song_game(request):
    return render(request, 'core/song_game.html')

def contests(request):
    return render(request, 'core/contests.html')

def results(request):
    return render(request, 'core/results.html')

def bias_selector(request):
    return render(request, 'core/bias_selector.html')

def live(request):
    return render(request, 'core/Live.html')

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
    return render(request, 'core/blog_page.html')

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
    now = timezone.now()
    # Get current and next month to ensure we have enough upcoming comebacks
    data_current = ComebackData.objects.filter(year=now.year, month=now.month).first()
    data_next = ComebackData.objects.filter(year=now.year if now.month < 12 else now.year + 1, 
                                            month=now.month + 1 if now.month < 12 else 1).first()
    
    all_releases = []
    if data_current:
        # Extract releases and add date info
        for date_key, details in data_current.data.items():
            if 'releases' in details:
                for r in details['releases']:
                    r['date_str'] = date_key
                    all_releases.append(r)
    
    if data_next:
        for date_key, details in data_next.data.items():
            if 'releases' in details:
                for r in details['releases']:
                    r['date_str'] = date_key
                    all_releases.append(r)

    # Sort by date (descending for timeline usually? Let's check the template's vibe. 
    # Usually, a timeline shows upcoming ones.)
    # Let's sort ascending for "upcoming"
    all_releases.sort(key=lambda x: x['date_str'])
    
    # Filter for today or later
    today_str = now.strftime('%Y-%m-%d')
    upcoming = [r for r in all_releases if r['date_str'] >= today_str]

    return render(request, 'core/comeback_timeline.html', {'comebacks': upcoming})


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

    albums = []
    events = []
    for y, m in months:
        data_obj = ComebackData.objects.filter(year=y, month=m).first()
        if not data_obj:
            continue
        for date_key, day_data in data_obj.data.items():
            # Releases matching this group
            for r in day_data.get('releases', []):
                if name_lower in r.get('artist', '').lower():
                    albums.append({
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
            # Birthdays matching this group
            for b in day_data.get('birthdays', []):
                if name_lower in (b.get('group', '') or '').lower() or name_lower in (b.get('name', '') or '').lower():
                    events.append({
                        'type': 'Birthday',
                        'title': f"{b.get('name', 'Member')} Birthday",
                        'date': date_key,
                        'iso_date': f"{date_key}T00:00:00Z" if date_key >= today_str else '',
                    })
            # Anniversaries matching this group
            for a in day_data.get('anniversaries', []):
                if name_lower in (a.get('group', '') or '').lower():
                    events.append({
                        'type': 'Anniversary',
                        'title': f"{group.name} Debut Anniversary",
                        'date': date_key,
                        'iso_date': f"{date_key}T00:00:00Z" if date_key >= today_str else '',
                    })

    albums.sort(key=lambda x: x['date_str'], reverse=True)
    events.sort(key=lambda x: x['date'])

    # Pull charted tracks if this group appears in the daily ranking
    tracks = []
    daily_rank = Ranking.objects.filter(timeframe='daily').first()
    if daily_rank and daily_rank.ranking_data:
        for item in daily_rank.ranking_data:
            if name_lower in item.get('artist', '').lower():
                tracks.append({
                    'title': item.get('track', ''),
                    'image': item.get('artwork_url', ''),
                    'album': item.get('album', ''),
                })

    context = {
        'group': group,
        'accent_color': accent_map.get(group.group_type, '#FF8EAF'),
        'accent_rgb': accent_rgb_map.get(group.group_type, '255,142,175'),
        'related_groups': related,
        'description': f"Explore the world of {group.name} — members, discography, top tracks, and more. Stay updated with the latest releases, events, and everything about {group.name} on K-Beats.",
        'members': [],
        'albums': albums,
        'tracks': tracks,
        'events': events,
        'gallery': [],
    }
    return render(request, 'core/idol_band_page.html', context)


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
