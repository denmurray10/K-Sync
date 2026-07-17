from __future__ import annotations

from typing import Dict

DEFAULT_TITLE = 'K-Pop Radio Online | Listen Live 24/7 | K-Beats'
DEFAULT_DESCRIPTION = (
    'Listen to K-pop radio online with K-Beats. Stream live 24/7, discover chart hits, '
    'follow new comebacks and request your favourite songs.'
)

SEO_BY_ROUTE: Dict[str, Dict[str, str]] = {
    'home': {
        'title': DEFAULT_TITLE,
        'description': DEFAULT_DESCRIPTION,
    },
    'live': {
        'title': 'Live K-Pop Stream | K-Beats Radio On Air 24/7',
        'description': 'Open the live K-pop stream on K-Beats Radio to see what is playing now, explore DJs, and request your favourite tracks.',
    },
    'charts': {
        'title': 'K-Pop Charts | Trending Songs and Artist Rankings on K-Beats',
        'description': 'Track trending K-pop songs and artist rankings with K-Beats charts, updated with fan momentum and fresh releases.',
    },
    'news': {
        'title': 'K-Pop News & New Music Discovery | K-Beats Editorial',
        'description': 'Read the latest K-pop news, comeback updates, artist stories and new music discovery coverage from the K-Beats editorial team.',
    },
    'idols': {
        'title': 'K-Pop Idols & Groups | Discover BTS, Stray Kids, TWICE and More',
        'description': 'Explore K-pop groups, member profiles and releases in the K-Beats Idol Universe with easy discovery and fan-focused detail.',
    },
    'schedule': {
        'title': 'K-Pop Radio Schedule | Live K-Beats Shows & Weekly Timetable',
        'description': 'View the K-Beats radio schedule with live show times, presenter slots and weekly programming for nonstop K-pop listening.',
    },
    'games': {
        'title': 'K-Pop Games | Play Free Fan Games on K-Beats',
        'description': 'Play free K-pop games including lyric challenges, trivia and chart battles on K-Beats.',
    },
    'request_track': {
        'title': 'Request K-Pop Songs Online | Ask K-Beats Radio To Play Your Track',
        'description': 'Request K-pop songs online with K-Beats Radio and send your favourite artist picks straight to the station queue.',
    },
    'comeback_timeline': {
        'title': 'K-Pop Comebacks & New Releases | Discover What Lands Next',
        'description': 'Follow upcoming K-pop comebacks, release dates and countdowns in the K-Beats comeback timeline.',
    },
    'blog_page': {
        'title': 'K-Pop Blog | Discover New K-Pop Music, Playlists and Guides',
        'description': 'Discover K-pop features, playlist guides, explainers and fan culture editorials in the K-Beats blog.',
    },
    'contests': {
        'title': 'K-Beats Contests | Enter K-Pop Giveaways and Fan Challenges',
        'description': 'Join K-Beats contests and giveaways for K-pop fans, with frequent challenges, perks and community rewards.',
    },
    'fan_clubs': {
        'title': 'K-Pop Fan Clubs | Join Communities and Unlock Rewards',
        'description': 'Join K-Beats fan clubs to support your favourite artists, unlock tier perks and take part in monthly events.',
    },
    'presenters': {
        'title': 'K-Beats Presenters | Meet the Voices Behind the Station',
        'description': 'Meet the K-Beats presenters and explore the personalities curating your daily K-pop listening experience.',
    },
    'stream_hub': {
        'title': 'K-Pop Stream Player Modes | K-Beats Stream Hub',
        'description': 'Browse K-Beats stream player modes for live K-pop listening, premium vibe presets, and quick routes back into the station.',
    },
    'pricing': {
        'title': 'K-Beats Pricing | Membership Plans and Fan Perks',
        'description': 'Compare K-Beats pricing plans and unlock premium fan perks, personalised experiences and exclusive content.',
    },
    'about_us': {
        'title': 'About K-Beats | Our Story, Mission and K-Pop Community',
        'description': 'Learn about K-Beats, our mission for global K-pop fans, and the team building a better community radio experience.',
    },
    'promo': {
        'title': 'K-Beats Mobile App | Listen To K-Pop Radio Anywhere',
        'description': 'Take K-Beats with you on mobile and keep live K-pop radio, fan perks, and station updates close wherever you listen.',
    },
}


def seo_defaults(request):
    route = ''
    if getattr(request, 'resolver_match', None):
        route = request.resolver_match.url_name or ''

    route_defaults = SEO_BY_ROUTE.get(route, {})

    return {
        'seo_title': route_defaults.get('title', DEFAULT_TITLE),
        'seo_description': route_defaults.get('description', DEFAULT_DESCRIPTION),
        'seo_type': 'website',
    }


def gamification(request):
    """Daily play streak for the header chip. Cheap: one indexed query, auth users only."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    try:
        from datetime import timedelta
        from django.utils import timezone as tz
        today = tz.now().date()
        window_start = today - timedelta(days=90)
        played_dates = set(
            user.game_scores.filter(played_at__date__gte=window_start)
            .values_list('played_at__date', flat=True)
        )
        if not played_dates:
            return {'play_streak': 0, 'played_today': False}
        played_today = today in played_dates
        # Streak counts back from today (or yesterday if not yet played today)
        cursor = today if played_today else today - timedelta(days=1)
        streak = 0
        while cursor in played_dates:
            streak += 1
            cursor -= timedelta(days=1)
        return {'play_streak': streak, 'played_today': played_today}
    except Exception:
        return {}


def for_you_pulse(request):
    """'For You' flyout data: bias comeback D-day, chart position/move, and
    Daily Drop day. Cached per (bias, chart day); auth users only."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    try:
        from datetime import datetime

        from django.core.cache import cache
        from django.urls import reverse
        from django.utils import timezone as tz

        from .models import ComebackData, Ranking, UserProfile

        profile = UserProfile.objects.select_related('bias').filter(user=user).first()
        bias = profile.bias if profile else None
        has_bias = bool(bias and (bias.name or '').strip())
        daily_rank = Ranking.objects.filter(timeframe='daily').first()

        pulse = {
            'has_bias': has_bias,
            'bias_name': bias.name.strip() if has_bias else '',
            'bias_url': reverse('idol_page', args=[bias.slug]) if has_bias and bias.slug else '',
            'chart': None,
            'comeback_dday': '',
            'comeback_title': '',
            'drop_day_number': 0,
            'drop_date': '',
        }
        if daily_rank:
            epoch = datetime(2026, 7, 1).date()
            pulse['drop_day_number'] = max(1, daily_rank.date.toordinal() - epoch.toordinal() + 1)
            pulse['drop_date'] = daily_rank.date.isoformat()

        if has_bias:
            chart_day = daily_rank.date.isoformat() if daily_rank else 'nochart'
            cache_key = f'foryou_pulse:{bias.pk}:{chart_day}'
            cached = cache.get(cache_key)
            if cached is None:
                cached = {'chart': None, 'comeback_dday': '', 'comeback_title': ''}
                name = bias.name.strip().lower()

                if daily_rank and daily_rank.ranking_data:
                    for idx, item in enumerate(daily_rank.ranking_data[:40]):
                        merged = f"{item.get('artist') or ''} {item.get('track') or ''}".lower()
                        if name in merged:
                            trend_raw = str(item.get('trend') or '')
                            digits = ''.join(ch for ch in trend_raw if ch.isdigit())
                            if '+' in trend_raw and digits:
                                trend = f'▲{digits}'
                            elif digits and '-' in trend_raw:
                                trend = f'▼{digits}'
                            else:
                                trend = ''
                            cached['chart'] = {
                                'rank': idx + 1,
                                'title': str(item.get('track') or '').strip(),
                                'trend': trend,
                            }
                            break

                now = tz.now()
                today_str = now.strftime('%Y-%m-%d')
                month_pairs = [(now.year, now.month)]
                month_pairs.append(
                    (now.year, now.month + 1) if now.month < 12 else (now.year + 1, 1)
                )
                best = None
                for year, month in month_pairs:
                    data_obj = ComebackData.objects.filter(year=year, month=month).first()
                    if not data_obj:
                        continue
                    for date_key, details in (data_obj.data or {}).items():
                        date_str = str(date_key).strip()
                        if date_str < today_str:
                            continue
                        for release in (details or {}).get('releases', []) or []:
                            merged = f"{release.get('artist') or ''} {release.get('title') or ''}".lower()
                            if name in merged and (best is None or date_str < best[0]):
                                best = (date_str, str(release.get('title') or '').strip())
                    if best:
                        break
                if best:
                    try:
                        release_date = datetime.strptime(best[0], '%Y-%m-%d').date()
                        days_out = (release_date - tz.localtime(now).date()).days
                        cached['comeback_dday'] = 'D-DAY' if days_out <= 0 else f'D-{days_out}'
                        cached['comeback_title'] = best[1]
                    except (TypeError, ValueError):
                        pass
                cache.set(cache_key, cached, 60 * 30)
            pulse.update(cached)

        return {'for_you_pulse': pulse}
    except Exception:
        return {}
