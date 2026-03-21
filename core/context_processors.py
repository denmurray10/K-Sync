from __future__ import annotations

from typing import Dict

DEFAULT_TITLE = 'K-Beats Radio | Live K-Pop Music, Charts, News & Community'
DEFAULT_DESCRIPTION = (
    'Stream live K-pop radio on K-Beats, discover charts and new releases, '
    'read K-pop news, join fan clubs, and stay connected with your favourite artists.'
)

SEO_BY_ROUTE: Dict[str, Dict[str, str]] = {
    'home': {
        'title': DEFAULT_TITLE,
        'description': DEFAULT_DESCRIPTION,
    },
    'live': {
        'title': 'K-Beats Live Radio | 24/7 K-Pop Station, DJs & Requests',
        'description': 'Listen to live K-pop radio 24/7 with K-Beats. Discover what is playing now, explore DJs, and request your favourite tracks.',
    },
    'charts': {
        'title': 'K-Pop Charts | Trending Songs and Artist Rankings on K-Beats',
        'description': 'Track trending K-pop songs and artist rankings with K-Beats charts, updated with fan momentum and fresh releases.',
    },
    'news': {
        'title': 'K-Pop News | Latest Comebacks, Releases and Fandom Updates',
        'description': 'Read the latest K-pop news, comeback updates, artist stories and fandom highlights from the K-Beats editorial team.',
    },
    'idols': {
        'title': 'K-Pop Idol Universe | Explore Groups, Members and Discographies',
        'description': 'Explore K-pop groups, member profiles and releases in the K-Beats Idol Universe with easy discovery and fan-focused detail.',
    },
    'schedule': {
        'title': 'K-Beats Radio Schedule | Shows, Hosts and Weekly Timetable',
        'description': 'View the K-Beats radio schedule with live show times, presenter slots and weekly programming for nonstop K-pop listening.',
    },
    'games': {
        'title': 'K-Pop Games | Play Free Fan Games on K-Beats',
        'description': 'Play free K-pop games including lyric challenges, trivia and chart battles on K-Beats.',
    },
    'comeback_timeline': {
        'title': 'K-Pop Comeback Timeline | Upcoming Releases and D-Day Alerts',
        'description': 'Follow upcoming K-pop comebacks, release dates and countdowns in the K-Beats comeback timeline.',
    },
    'blog_page': {
        'title': 'K-Beats Blog | K-Pop Features, Guides and Editorials',
        'description': 'Discover K-pop features, explainers and fan culture editorials in the K-Beats blog.',
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
