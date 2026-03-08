import json
import logging
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
from openai import OpenAI
from .models import (
    Ranking, ComebackData, KPopGroup, KPopMember,
    LivePoll, BlogArticle, UserProfile, FavouriteSong,
    GameScore, SongRequest,
)

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
        return JsonResponse({'success': False, 'error': 'Missing fields'}, status=400)

    recent_requests = SongRequest.objects.all()[:10]
    return render(request, 'core/request_track.html', {
        'recent_requests': recent_requests,
    })


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
    return render(request, 'core/contests.html')

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


def blog_generate(request):
    """Generate articles from RSS feed via DeepSeek Reasoner."""
    import re
    from django.utils.text import slugify
    from django.shortcuts import redirect

    articles = _fetch_kpop_news()
    created = 0

    # Gather existing article slugs/titles for SEO inter-linking hints
    existing_articles = list(
        BlogArticle.objects.values('slug', 'title')[:15]
    )

    for item in articles:
        title = item.get('title', '').strip()
        if not title:
            continue

        base_slug = slugify(title)[:180]
        if BlogArticle.objects.filter(slug=base_slug).exists():
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
        body = raw
        if '---' in raw:
            header, body = raw.split('---', 1)
            for line in header.strip().splitlines():
                if line.upper().startswith('SUBTITLE:'):
                    subtitle = line.split(':', 1)[1].strip()
                    break

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

        BlogArticle.objects.create(
            slug=base_slug,
            title=title,
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

        # Keep inter-linking list current for subsequent articles
        existing_articles.append({'slug': base_slug, 'title': title})

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
