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

_news_cache = {'articles': [], 'ts': 0}

def news(request):
    articles = _fetch_kpop_news()
    featured = articles[0] if articles else None
    remaining = articles[1:] if len(articles) > 1 else []

    cats = []
    seen = set()
    for a in articles:
        if a['category'] not in seen:
            seen.add(a['category'])
            cats.append(a['category'])

    return render(request, 'core/news.html', {
        'featured': featured,
        'articles': remaining,
        'all_articles': articles,
        'categories': cats,
        'total_count': len(articles),
    })


def _fetch_kpop_news():
    import re
    import time
    import xml.etree.ElementTree as ET
    from datetime import datetime

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

    articles = []
    feeds = [
        'https://news.google.com/rss/search?q=kpop+OR+k-pop+when:7d&hl=en-US&gl=US&ceid=US:en',
    ]

    for url in feeds:
        try:
            resp = requests.get(
                url, timeout=8,
                headers={'User-Agent': 'K-Beats/1.0'},
            )
            if resp.status_code != 200:
                continue

            root = ET.fromstring(resp.content)
            for item in root.iter('item'):
                title_raw = item.findtext('title', '')
                parts = title_raw.rsplit(' - ', 1)
                title = parts[0].strip()
                source = (
                    parts[1].strip() if len(parts) > 1
                    else 'K-Pop News'
                )

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
                    'source': source,
                    'link': link,
                    'date': date_str,
                    'time_ago': time_ago,
                    'category': cat,
                    'excerpt': excerpt,
                    'image': img,
                })
        except Exception:
            pass

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
        f"?id={int(collection_id)}&entity=song"
    )
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0'}
    )
    album_info = {}
    tracks = []
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            for item in data.get('results', []):
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
    except Exception as e:
        logger.warning(
            "iTunes album lookup failed for %s: %s",
            collection_id, e
        )

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
