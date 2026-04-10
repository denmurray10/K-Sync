from __future__ import annotations

from typing import Dict

DEFAULT_TITLE = 'K-Pop Radio Online | Live K-Pop Stream UK | K-Beats Radio'
DEFAULT_DESCRIPTION = (
    'Listen to K-pop radio online with K-Beats Radio. Stream live K-pop, discover charts and new releases, '
    'read K-pop news, and stay connected with your favourite artists.'
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
    'pricing': {
        'title': 'K-Beats Pricing | Membership Plans and Fan Perks',
        'description': 'Compare K-Beats pricing plans and unlock premium fan perks, personalised experiences and exclusive content.',
    },
    'about_us': {
        'title': 'About K-Beats | Our Story, Mission and K-Pop Community',
        'description': 'Learn about K-Beats, our mission for global K-pop fans, and the team building a better community radio experience.',
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
