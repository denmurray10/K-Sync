from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.test.client import RequestFactory
from datetime import datetime, timedelta, timezone as datetime_timezone
import io
import os
import tempfile
from django.contrib.auth.models import User
from django.db import connection
from django.core.cache import cache
from unittest.mock import Mock, patch
from PIL import Image

from core import views as core_views
from core import scheduler as core_scheduler

from .models import (
    BlogArticle,
    ComebackData,
    Contest,
    KPopGroup,
    LivePoll,
    LivePollOption,
    FanClubMembership,
    LimitedTimeEvent,
    EventBadgeDrop,
    EventParticipation,
    RadioTrack,
    UserBadge,
)


class BlogArticleSanitizationTests(TestCase):
    def test_save_sanitizes_disallowed_tags_and_attrs(self):
        article = BlogArticle.objects.create(
            slug='sanitize-1',
            title='Sanitize Test',
            subtitle='',
            category='news',
            source_title='Source',
            source_url='https://example.com',
            source_name='Example',
            image='',
            image_2='',
            body_html=(
                '<p>Hello</p><script>alert(1)</script>'
                '<a href="https://safe.example" onclick="evil()">link</a>'
            ),
            reading_time=1,
        )

        self.assertIn('<p>Hello</p>', article.body_html)
        self.assertNotIn('<script>', article.body_html)
        self.assertNotIn('onclick=', article.body_html)
        self.assertIn(
            '<a href="https://safe.example">link</a>',
            article.body_html,
        )

    def test_save_keeps_allowed_structure_and_handles_none(self):
        article = BlogArticle.objects.create(
            slug='sanitize-2',
            title='Allowed Tags Test',
            subtitle='',
            category='news',
            source_title='Source',
            source_url='https://example.com',
            source_name='Example',
            image='',
            image_2='',
            body_html=None,
            reading_time=1,
        )
        self.assertEqual(article.body_html, '')

        article.body_html = (
            '<p><strong>ok</strong> <em>fine</em></p>'
            '<h3>Header</h3><ul><li>One</li></ul>'
        )
        article.save()

        self.assertIn(
            '<p><strong>ok</strong> <em>fine</em></p>',
            article.body_html,
        )
        self.assertIn('<h3>Header</h3>', article.body_html)
        self.assertIn('<ul><li>One</li></ul>', article.body_html)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class SiteIconTests(TestCase):
    def test_seo_partial_uses_local_favicon_assets(self):
        request = RequestFactory().get('/')
        rendered = render_to_string('core/seo_meta.html', {'request': request})

        self.assertIn('href="/static/core/img/favicon.ico"', rendered)
        self.assertIn('href="/static/core/img/favicon-32x32.png"', rendered)
        self.assertIn('href="/static/core/img/apple-touch-icon.png"', rendered)
        self.assertIn('href="/static/core/site.webmanifest"', rendered)

    def test_root_favicon_redirects_to_static_asset(self):
        response = self.client.get('/favicon.ico')

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/static/core/img/favicon.ico')


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class SeoRolloutTests(TestCase):
    def setUp(self):
        self.group = KPopGroup.objects.create(
            name='Signal Queens',
            slug='signal-queens',
            label='Signal Label',
            group_type='GIRL',
            description='Signal Queens are a rising K-pop group known for glossy hooks and midnight-pop choruses.',
            rank=7,
        )
        self.contest = Contest.objects.create(
            slug='signal-queens-giveaway',
            title='Signal Queens Signed Album Giveaway',
            subtitle='Win signed merch and album rewards from the latest Signal Queens era.',
            description='A fan giveaway for the latest Signal Queens comeback.',
            artist='Signal Queens',
            prizes=[{'title': 'Signed album'}],
            rules='One entry per person',
            entry_question='What is your favourite track?',
            deadline=timezone.now() + timedelta(days=5),
            is_active=True,
        )

    def test_homepage_uses_dynamic_seo_metadata(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, '<title>K-Pop Radio Online | Live K-Pop Stream UK | K-Beats Radio</title>', html=True)
        self.assertContains(response, 'Listen to K-pop radio online with K-Beats Radio.')
        self.assertContains(response, reverse('uk_kpop_radio'))

    def test_keyword_landing_pages_render_and_include_unique_h1(self):
        pages = [
            ('uk_kpop_radio', 'K-Pop Radio Station UK'),
            ('midnight_kpop_vibes', 'Midnight K-Pop Vibes'),
            ('rainy_day_kpop', 'Rainy Day K-Pop'),
            ('late_night_kpop_music', 'Late Night K-Pop Music'),
            ('best_kpop_playlist_2026', 'Best K-Pop Playlist 2026'),
            ('discover_new_kpop_music', 'Discover New K-Pop Music'),
        ]

        for url_name, heading in pages:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, heading)

    def test_sitemap_contains_new_seo_destinations(self):
        response = self.client.get(reverse('django.contrib.sitemaps.views.sitemap'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('uk_kpop_radio'))
        self.assertContains(response, reverse('midnight_kpop_vibes'))
        self.assertContains(response, reverse('best_kpop_playlist_2026'))
        self.assertContains(response, reverse('discover_new_kpop_music'))

    def test_non_seo_routes_emit_noindex_headers(self):
        routes = [
            reverse('preview_404'),
            reverse('home_redesign_lab'),
            reverse('upcoming_comebacks_design_lab'),
            reverse('test_page'),
            reverse('test_landing_wow_hero'),
            reverse('placeholder'),
            reverse('login'),
            reverse('signup'),
            reverse('results'),
        ]

        for route in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')

    def test_public_pages_now_emit_route_specific_titles(self):
        page_expectations = [
            ('charts', 'Daily K-Pop Songs Chart | K-Beats Charts'),
            ('request_track', 'Request K-Pop Songs Online | Ask K-Beats Radio To Play Your Track'),
            ('contests', 'K-Beats Contests | Enter K-Pop Giveaways and Fan Challenges'),
            ('fan_clubs', 'K-Pop Fan Clubs | Join Communities and Unlock Rewards'),
            ('stream_hub', 'K-Pop Stream Player Modes | K-Beats Stream Hub'),
            ('pricing', 'K-Beats Pricing | Membership Plans and Fan Perks'),
            ('about_us', 'About K-Beats | Our Story, Mission and K-Pop Community'),
            ('presenters', 'K-Beats Presenters | Meet the Voices Behind the Station'),
            ('promo', 'K-Beats Mobile App | Listen To K-Pop Radio Anywhere'),
        ]

        for route_name, expected_title in page_expectations:
            response = self.client.get(reverse(route_name))
            self.assertContains(response, f'<title>{expected_title}</title>', html=True)

    def test_dynamic_artist_and_contest_pages_emit_unique_titles(self):
        idol_response = self.client.get(reverse('idol_page', args=[self.group.slug]))
        contest_response = self.client.get(reverse('contest_entry', args=[self.contest.slug]))

        self.assertContains(
            idol_response,
            '<title>Signal Queens K-Pop Group Guide | Songs, Members and Albums | K-Beats</title>',
            html=True,
        )
        self.assertContains(
            contest_response,
            '<title>Signal Queens Signed Album Giveaway | Enter This K-Pop Contest on K-Beats</title>',
            html=True,
        )

    def test_core_discovery_pages_show_distinct_keyword_led_hero_copy(self):
        home_response = self.client.get(reverse('home'))
        listen_free_response = self.client.get(reverse('listen_free_landing'))
        live_response = self.client.get(reverse('live'))
        idols_response = self.client.get(reverse('idols'))
        comebacks_response = self.client.get(reverse('comebacks'))

        self.assertContains(home_response, 'K-POP RADIO')
        self.assertContains(home_response, 'ONLINE')
        self.assertContains(listen_free_response, 'Free K-Pop Radio,')
        self.assertContains(listen_free_response, 'No app. No card. No download. Just hit play.')
        self.assertContains(live_response, 'Live K-Pop Stream')
        self.assertContains(live_response, 'Real-time now playing on K-Beats Radio')
        self.assertContains(idols_response, 'K-POP')
        self.assertContains(idols_response, 'IDOLS')
        self.assertContains(comebacks_response, 'COMEBACKS')


class FanClubTierAndEventTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tier-user', password='secret123')
        self.group = KPopGroup.objects.create(
            name='TEST GROUP',
            slug='test-group',
            label='Test Label',
            group_type='GIRL',
        )

    def test_vote_poll_blocks_non_premium_during_early_access(self):
        poll = LivePoll.objects.create(
            question='Who wins this chart battle?',
            is_active=True,
            early_access_starts_at=timezone.now() + timedelta(hours=6),
            early_access_group=self.group,
            early_access_min_tier='PLUS',
        )
        option = LivePollOption.objects.create(poll=poll, text='Team A')

        self.client.login(username='tier-user', password='secret123')

        blocked = self.client.post(
            reverse('vote_poll'),
            data={'option_id': option.id},
            content_type='application/json',
        )
        self.assertEqual(blocked.status_code, 403)

        FanClubMembership.objects.create(user=self.user, group=self.group, tier='PLUS')
        allowed = self.client.post(
            reverse('vote_poll'),
            data={'option_id': option.id},
            content_type='application/json',
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json().get('success'))

    def test_event_badge_claim_requires_votes_and_tier(self):
        event = LimitedTimeEvent.objects.create(
            title='Monthly Badge Drop',
            slug='monthly-badge-drop',
            event_type='BADGE_DROP',
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        badge_drop = EventBadgeDrop.objects.create(
            event=event,
            badge_name='Spotlight Collector',
            rarity='EPIC',
            minimum_tier='ULTRA',
            min_votes_required=2,
            is_active=True,
        )

        FanClubMembership.objects.create(user=self.user, group=self.group, tier='PLUS')
        EventParticipation.objects.create(user=self.user, event=event, votes_cast=3)

        self.client.login(username='tier-user', password='secret123')
        tier_blocked = self.client.post(
            reverse('api_event_claim_badge'),
            data={'badge_drop_id': badge_drop.id},
            content_type='application/json',
        )
        self.assertEqual(tier_blocked.status_code, 403)

        membership = FanClubMembership.objects.get(user=self.user, group=self.group)
        membership.tier = 'ULTRA'
        membership.save(update_fields=['tier'])

        claimed = self.client.post(
            reverse('api_event_claim_badge'),
            data={'badge_drop_id': badge_drop.id},
            content_type='application/json',
        )
        self.assertEqual(claimed.status_code, 200)
        self.assertTrue(claimed.json().get('claimed'))
        self.assertTrue(UserBadge.objects.filter(user=self.user, name='Spotlight Collector').exists())


class ComebackPerformanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.group = KPopGroup.objects.create(
            name='Alpha Group',
            slug='alpha-group',
            label='Alpha Label',
            group_type='GIRL',
            rank=1,
        )
        today = timezone.localdate()
        self.nav_year = today.year
        self.nav_month = today.month
        date_key = today.isoformat()
        ComebackData.objects.create(
            year=self.nav_year,
            month=self.nav_month,
            data={
                date_key: {
                    'releases': [
                        {
                            'artist': 'Alpha Group',
                            'title': 'Signal Rush',
                            'type': 'Single',
                            'image': 'https://example.com/a.jpg',
                        },
                        {
                            'artist': 'Beta Unit',
                            'title': 'Night Shift',
                            'type': 'EP',
                            'image': 'https://example.com/b.jpg',
                        },
                    ],
                    'birthdays': [
                        {
                            'name': 'Rin',
                            'group': 'Alpha Group',
                            'age': 23,
                            'image': 'https://example.com/rin.jpg',
                        }
                    ],
                    'anniversaries': [
                        {
                            'group': 'Alpha Group',
                            'years': 5,
                            'image': 'https://example.com/anniversary.jpg',
                        }
                    ],
                }
            },
        )

    def test_comeback_timeline_renders_with_low_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('comeback_timeline'))

        self.assertEqual(response.status_code, 200)
        self.assertLess(len(queries), 20)
        self.assertContains(response, 'COMEBACK')

    def test_release_drawer_endpoint_returns_expected_payload(self):
        timeline_response = self.client.get(reverse('comeback_timeline'))
        self.assertEqual(timeline_response.status_code, 200)

        today = timezone.localdate()
        window_data = core_views._load_comeback_window_content(today, today.year, today.month)
        release_id = window_data['all_releases'][0]['id']

        response = self.client.get(
            reverse('comeback_release_drawer_api', args=[release_id]),
            {'year': today.year, 'month': today.month},
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['id'], release_id)
        self.assertIn('same_day_lineup', payload)
        self.assertIn('nearby_releases', payload)
        self.assertIn('day_birthdays', payload)
        self.assertIn('day_anniversaries', payload)

    def test_day_drawer_endpoint_returns_expected_payload(self):
        today = timezone.localdate()
        response = self.client.get(
            reverse('comeback_day_drawer_api', args=[today.isoformat()]),
            {'year': today.year, 'month': today.month},
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['date_str'], today.isoformat())
        self.assertEqual(payload['release_count'], 2)
        self.assertEqual(payload['birthday_count'], 1)
        self.assertEqual(payload['anniversary_count'], 1)

    def test_comeback_window_cache_invalidates_on_data_update(self):
        today = timezone.localdate()
        first = core_views._load_comeback_window_content(today, today.year, today.month)
        self.assertEqual(first['all_releases'][0]['title'], 'Signal Rush')

        record = ComebackData.objects.get(year=today.year, month=today.month)
        updated = dict(record.data)
        updated[today.isoformat()] = dict(updated[today.isoformat()])
        updated[today.isoformat()]['releases'] = [
            {
                'artist': 'Alpha Group',
                'title': 'Updated Signal',
                'type': 'Single',
                'image': 'https://example.com/a.jpg',
            }
        ]
        record.data = updated
        record.save()

        second = core_views._load_comeback_window_content(today, today.year, today.month)
        self.assertEqual(second['all_releases'][0]['title'], 'Updated Signal')


class ComebackNewsSyncTests(TestCase):
    def setUp(self):
        cache.clear()
        today = timezone.localdate()
        self.group = KPopGroup.objects.create(
            name='Signal Unit',
            slug='signal-unit',
            label='Signal Label',
            group_type='GIRL',
            rank=1,
        )
        self.date_key = (today - timedelta(days=1)).isoformat()
        ComebackData.objects.create(
            year=today.year,
            month=today.month,
            data={
                self.date_key: {
                    'releases': [
                        {
                            'artist': 'Signal Unit',
                            'title': 'Echo Bloom',
                            'type': 'Single',
                            'image': 'https://example.com/echo.jpg',
                        }
                    ],
                    'birthdays': [],
                    'anniversaries': [],
                }
            },
        )

    def test_comeback_timeline_persists_landed_release_as_blog_article(self):
        response = self.client.get(reverse('comeback_timeline'))
        self.assertEqual(response.status_code, 200)

        article = BlogArticle.objects.get(slug__contains='echo-bloom')
        self.assertEqual(article.category, 'Comeback')
        self.assertIn('Echo Bloom', article.title)

    def test_news_page_can_surface_synced_comeback_article(self):
        self.client.get(reverse('comeback_timeline'))
        response = self.client.get(reverse('news'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Echo Bloom')


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class WhatJustLandedReelLabTests(TestCase):
    def setUp(self):
        cache.clear()
        self.articles = [
            BlogArticle.objects.create(
                slug='ph1-purple-tape',
                title='pH-1 - PURPLE TAPE: What Just Landed',
                subtitle='pH-1 just landed with PURPLE TAPE, a album release arriving on Thursday 09 Apr.',
                category='Comeback',
                source_title='Comeback Signal Hub',
                source_url='https://example.com/source/ph1',
                source_name='K-Beats',
                image='https://example.com/ph1.jpg',
                image_2='',
                image_3='',
                body_html='<p>Signal copy.</p>',
                reading_time=3,
            ),
            BlogArticle.objects.create(
                slug='bambam-ready-for-more',
                title='BamBam - Ready For MORE: What Just Landed',
                subtitle='BamBam just landed with Ready For MORE, a single release arriving on Wednesday 25 Mar.',
                category='Comeback',
                source_title='Comeback Signal Hub',
                source_url='https://example.com/source/bambam',
                source_name='K-Beats',
                image='https://example.com/bambam.jpg',
                image_2='',
                image_3='',
                body_html='<p>Signal copy.</p>',
                reading_time=3,
            ),
            BlogArticle.objects.create(
                slug='long-title-sample',
                title='SORAN - Change: Tonight, I\'m Afraid of the First Date: What Just Landed',
                subtitle='SORAN just landed with Change: Tonight, I\'m Afraid of the First Date, a single release arriving on Friday 10 Apr.',
                category='Comeback',
                source_title='Comeback Signal Hub',
                source_url='https://example.com/source/soran',
                source_name='K-Beats',
                image='https://example.com/soran.jpg',
                image_2='',
                image_3='',
                body_html='<p>Signal copy.</p>',
                reading_time=3,
            ),
            BlogArticle.objects.create(
                slug='ifeye-as-if',
                title='ifeye - As If: What Just Landed',
                subtitle='ifeye just landed with As If, a ep release arriving on Wednesday 15 Apr.',
                category='Comeback',
                source_title='Comeback Signal Hub',
                source_url='https://example.com/source/ifeye',
                source_name='K-Beats',
                image='',
                image_2='',
                image_3='',
                body_html='<p>Signal copy.</p>',
                reading_time=3,
            ),
        ]

    def test_reel_lab_renders_three_image_samples_and_one_fallback(self):
        response = self.client.get(reverse('what_just_landed_reel_lab'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'What Just Landed Reel Lab')
        reel_articles = response.context['reel_articles']
        self.assertEqual(len(reel_articles), 4)
        self.assertEqual(sum(1 for item in reel_articles if item['has_image']), 3)
        self.assertEqual(sum(1 for item in reel_articles if item['is_fallback_sample']), 1)

    def test_reel_lab_preserves_exact_titles_and_builds_layout_styles(self):
        response = self.client.get(reverse('what_just_landed_reel_lab'))

        reel_articles = response.context['reel_articles']
        titles = [item['title'] for item in reel_articles]
        self.assertIn(
            "SORAN - Change: Tonight, I'm Afraid of the First Date: What Just Landed",
            titles,
        )
        fallback_item = next(item for item in reel_articles if item['is_fallback_sample'])
        self.assertEqual(fallback_item['title'], 'ifeye - As If: What Just Landed')
        self.assertIn('font-size:', fallback_item['title_style'])

    def test_select_next_reel_article_skips_already_published_reels(self):
        first_article = BlogArticle.objects.order_by('created_at').first()
        first_article.facebook_reel_id = 'reel_123'
        first_article.save(update_fields=['facebook_reel_id'])

        selected = core_views._select_next_what_just_landed_reel_article()

        self.assertIsNotNone(selected)
        self.assertNotEqual(selected.pk, first_article.pk)
        self.assertEqual(selected.slug, 'bambam-ready-for-more')

    def test_select_next_reel_article_skips_preview_ready_articles(self):
        first_article = BlogArticle.objects.order_by('created_at').first()
        first_article.facebook_reel_preview_status = 'ready'
        first_article.facebook_reel_publish_status = 'scheduled'
        first_article.facebook_reel_preview_video_path = 'generated/facebook_reels/test.mp4'
        first_article.facebook_reel_publish_scheduled_at = timezone.now() + timedelta(minutes=20)
        first_article.save(update_fields=[
            'facebook_reel_preview_status',
            'facebook_reel_publish_status',
            'facebook_reel_preview_video_path',
            'facebook_reel_publish_scheduled_at',
        ])

        selected = core_views._select_next_what_just_landed_reel_article()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.slug, 'bambam-ready-for-more')

    def test_select_next_ready_reel_preview_returns_expired_preview(self):
        article = BlogArticle.objects.get(slug='ph1-purple-tape')
        article.facebook_reel_preview_status = 'ready'
        article.facebook_reel_publish_status = 'scheduled'
        article.facebook_reel_preview_video_path = 'generated/facebook_reels/test.mp4'
        article.facebook_reel_publish_scheduled_at = timezone.now() - timedelta(minutes=1)
        article.save(update_fields=[
            'facebook_reel_preview_status',
            'facebook_reel_publish_status',
            'facebook_reel_preview_video_path',
            'facebook_reel_publish_scheduled_at',
        ])

        selected = core_views._select_next_ready_what_just_landed_reel_preview()

        self.assertIsNotNone(selected)
        self.assertEqual(selected.pk, article.pk)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('core.views._download_what_just_landed_reel_source_image')
    def test_render_reel_frame_returns_vertical_image(self, mock_download):
        mock_download.return_value = Image.new('RGB', (1400, 1400), '#4f2ddf')
        article = BlogArticle.objects.get(slug='ph1-purple-tape')
        payload = core_views._build_what_just_landed_reel_preview_payload(article, sequence=0)

        frame = core_views._render_what_just_landed_reel_frame(payload, 0.5)

        self.assertEqual(frame.size, (1080, 1920))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('core.views._render_what_just_landed_reel_video')
    def test_generate_reel_preview_updates_hold_tracking(self, mock_render):
        article = BlogArticle.objects.get(slug='ph1-purple-tape')
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False, dir=tempfile.gettempdir()) as handle:
            handle.write(b'preview-video-bytes')
            temp_video_path = handle.name

        self.addCleanup(lambda: os.path.exists(temp_video_path) and os.remove(temp_video_path))
        mock_render.return_value = temp_video_path

        with self.settings(FACEBOOK_REELS_PREVIEW_HOLD_MINUTES=20):
            result = core_views._generate_what_just_landed_reel_preview(article)

        article.refresh_from_db()
        self.assertEqual(article.facebook_reel_preview_status, 'ready')
        self.assertEqual(article.facebook_reel_publish_status, 'scheduled')
        self.assertTrue(article.facebook_reel_preview_video_path.endswith('.mp4'))
        self.assertTrue(bool(article.facebook_reel_preview_created_at))
        self.assertTrue(bool(article.facebook_reel_publish_scheduled_at))
        self.assertEqual(
            article.facebook_reel_publish_scheduled_at - article.facebook_reel_preview_created_at,
            timedelta(minutes=20),
        )
        self.assertIn(article.slug, result['preview_url'])
        self.assertIn(result['mode'], {'preview_created', 'preview_created_and_scheduled'})

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('core.views.requests.post')
    def test_schedule_facebook_reel_publication_uses_meta_scheduled_state(self, mock_post):
        article = BlogArticle.objects.get(slug='ph1-purple-tape')
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False, dir=tempfile.gettempdir()) as handle:
            handle.write(b'scheduled-video-bytes')
            temp_video_path = handle.name

        self.addCleanup(lambda: os.path.exists(temp_video_path) and os.remove(temp_video_path))

        start_response = Mock()
        start_response.status_code = 200
        start_response.json.return_value = {
            'video_id': 'scheduled_123',
            'upload_url': 'https://upload.facebook.example/reel',
        }
        upload_response = Mock()
        upload_response.status_code = 200
        upload_response.json.return_value = {'success': True}
        finish_response = Mock()
        finish_response.status_code = 200
        finish_response.json.return_value = {'success': True}
        mock_post.side_effect = [start_response, upload_response, finish_response]

        publish_at = timezone.now() + timedelta(minutes=20)
        with self.settings(
            FACEBOOK_PAGE_ID='123456',
            FACEBOOK_PAGE_ACCESS_TOKEN='page-token',
        ):
            result = core_views._schedule_facebook_reel_publication(article, temp_video_path, publish_at)

        article.refresh_from_db()
        self.assertEqual(article.facebook_reel_id, 'scheduled_123')
        self.assertEqual(article.facebook_reel_publish_status, 'scheduled')
        self.assertEqual(result['video_id'], 'scheduled_123')
        finish_call = mock_post.call_args_list[2]
        self.assertEqual(finish_call.kwargs['params']['video_state'], 'SCHEDULED')
        self.assertEqual(finish_call.kwargs['params']['scheduled_publish_time'], int(publish_at.timestamp()))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    @patch('core.views._render_what_just_landed_reel_video')
    @patch('core.views._poll_facebook_reel_status')
    @patch('core.views.requests.post')
    def test_publish_ready_facebook_reel_preview_updates_article_tracking(self, mock_post, mock_poll, mock_render):
        article = BlogArticle.objects.get(slug='ph1-purple-tape')
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as handle:
            handle.write(b'fake-video-bytes')
            temp_video_path = handle.name

        self.addCleanup(lambda: os.path.exists(temp_video_path) and os.remove(temp_video_path))
        mock_poll.return_value = {'status': {'video_status': 'ready'}}
        article.facebook_reel_preview_video_path = os.path.relpath(temp_video_path, tempfile.gettempdir()).replace('\\', '/')
        article.facebook_reel_preview_status = 'ready'
        article.facebook_reel_publish_status = 'scheduled'
        article.facebook_reel_publish_scheduled_at = timezone.now() - timedelta(minutes=1)
        article.save(update_fields=[
            'facebook_reel_preview_video_path',
            'facebook_reel_preview_status',
            'facebook_reel_publish_status',
            'facebook_reel_publish_scheduled_at',
        ])

        start_response = Mock()
        start_response.status_code = 200
        start_response.json.return_value = {
            'video_id': '987654321',
            'upload_url': 'https://upload.facebook.example/reel',
        }
        upload_response = Mock()
        upload_response.status_code = 200
        upload_response.json.return_value = {'success': True}
        finish_response = Mock()
        finish_response.status_code = 200
        finish_response.json.return_value = {'success': True}
        mock_post.side_effect = [start_response, upload_response, finish_response]

        with self.settings(
            FACEBOOK_PAGE_ID='123456',
            FACEBOOK_PAGE_ACCESS_TOKEN='page-token',
            FACEBOOK_REELS_ENABLED=True,
            FACEBOOK_REELS_STATUS_POLL_ATTEMPTS=1,
            FACEBOOK_REELS_STATUS_POLL_SECONDS=1,
        ):
            result = core_views._publish_ready_what_just_landed_reel_preview(article)

        article.refresh_from_db()
        self.assertEqual(article.facebook_reel_id, '987654321')
        self.assertTrue(bool(article.facebook_reel_posted_at))
        self.assertTrue(article.facebook_reel_video_path.endswith('.mp4'))
        self.assertEqual(article.facebook_reel_preview_status, 'published')
        self.assertEqual(article.facebook_reel_publish_status, 'published')
        self.assertEqual(result['video_id'], '987654321')
        self.assertEqual(mock_post.call_count, 3)
        mock_render.assert_not_called()

    def test_private_reel_preview_page_embeds_saved_video(self):
        article = BlogArticle.objects.get(slug='ph1-purple-tape')
        article.facebook_reel_preview_video_path = 'generated/facebook_reels/ph1-preview.mp4'
        article.facebook_reel_preview_status = 'ready'
        article.facebook_reel_publish_status = 'scheduled'
        article.facebook_reel_preview_created_at = timezone.now()
        article.facebook_reel_publish_scheduled_at = timezone.now() + timedelta(minutes=20)
        article.save(update_fields=[
            'facebook_reel_preview_video_path',
            'facebook_reel_preview_status',
            'facebook_reel_publish_status',
            'facebook_reel_preview_created_at',
            'facebook_reel_publish_scheduled_at',
        ])

        response = self.client.get(
            reverse('what_just_landed_reel_preview', kwargs={'slug': article.slug, 'token': article.facebook_reel_preview_token})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, article.title)
        self.assertContains(response, '/media/generated/facebook_reels/ph1-preview.mp4')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')


class FacebookArticlePostingTests(TestCase):
    def setUp(self):
        self.article = BlogArticle.objects.create(
            slug='fb-image-post-test',
            title='Image Post Test',
            subtitle='A subtitle for the post.',
            category='Comeback',
            source_title='Source',
            source_url='https://example.com/source',
            source_name='Example',
            image='https://example.com/post-image.jpg',
            image_2='',
            image_3='',
            body_html='<p>First paragraph for Facebook.</p>',
            reading_time=2,
        )

    @patch('core.views.requests.post')
    def test_post_to_facebook_uses_photo_endpoint_and_marks_article_posted(self, mock_post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            'id': 'photo_123',
            'post_id': 'page_456_post_789',
        }
        mock_post.return_value = response

        with self.settings(
            FACEBOOK_PAGE_ID='page_456',
            FACEBOOK_PAGE_ACCESS_TOKEN='page-token',
        ):
            core_views._post_to_facebook_draft(self.article)

        self.article.refresh_from_db()
        self.assertEqual(self.article.facebook_post_id, 'page_456_post_789')
        self.assertIsNotNone(self.article.facebook_posted_at)
        mock_post.assert_called_once()
        self.assertIn('/photos', mock_post.call_args.args[0])
        self.assertEqual(
            mock_post.call_args.kwargs['data']['url'],
            'https://example.com/post-image.jpg',
        )
        self.assertIn('caption', mock_post.call_args.kwargs['data'])
        self.assertNotIn('link', mock_post.call_args.kwargs['data'])

    @patch('core.views.requests.get')
    @patch('core.views.requests.post')
    def test_comment_pass_skips_articles_already_marked_posted(self, mock_post, mock_get):
        self.article.facebook_post_id = 'page_456_post_789'
        self.article.facebook_posted_at = timezone.now()
        self.article.save(update_fields=['facebook_post_id', 'facebook_posted_at'])

        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.json.return_value = {'data': [{'id': 'page_456_post_789'}]}

        with self.settings(
            FACEBOOK_HOMEPAGE_COMMENT_ENABLED=True,
            FACEBOOK_HOMEPAGE_COMMENT_TEXT='https://kbeatsradio.co.uk/',
            FACEBOOK_PAGE_ID='page_456',
            FACEBOOK_PAGE_ACCESS_TOKEN='page-token',
        ):
            created = core_views._comment_on_live_facebook_posts()

        self.assertEqual(created, 0)
        mock_post.assert_not_called()

    @patch('core.views._post_to_facebook_draft')
    def test_post_next_article_to_facebook_respects_queue_start_date(self, mock_publish):
        older_article = BlogArticle.objects.create(
            slug='fb-older-than-cutoff',
            title='Older Than Cutoff',
            subtitle='',
            category='News',
            source_title='Source',
            source_url='https://example.com/older',
            source_name='Example',
            image='https://example.com/older.jpg',
            image_2='',
            image_3='',
            body_html='<p>Older article.</p>',
            reading_time=1,
        )
        newer_article = BlogArticle.objects.create(
            slug='fb-newer-than-cutoff',
            title='Newer Than Cutoff',
            subtitle='',
            category='News',
            source_title='Source',
            source_url='https://example.com/newer',
            source_name='Example',
            image='https://example.com/newer.jpg',
            image_2='',
            image_3='',
            body_html='<p>Newer article.</p>',
            reading_time=1,
        )
        BlogArticle.objects.filter(pk=older_article.pk).update(
            created_at=datetime(2026, 3, 25, 23, 0, tzinfo=datetime_timezone.utc)
        )
        BlogArticle.objects.filter(pk=newer_article.pk).update(
            created_at=datetime(2026, 3, 26, 0, 10, tzinfo=datetime_timezone.utc)
        )

        def publish_side_effect(article):
            article.facebook_post_id = f'post-{article.pk}'
            article.facebook_posted_at = timezone.now()
            article.save(update_fields=['facebook_post_id', 'facebook_posted_at'])

        mock_publish.side_effect = publish_side_effect

        with self.settings(
            FACEBOOK_POST_ENABLED=True,
            FACEBOOK_POST_QUEUE_START_DATE='2026-03-26',
        ):
            result = core_views._post_next_article_to_facebook()

        self.assertTrue(result)
        mock_publish.assert_called_once()
        self.assertEqual(mock_publish.call_args.args[0].slug, 'fb-newer-than-cutoff')


class FacebookReelsSchedulerTests(TestCase):
    @patch('core.scheduler.BackgroundScheduler')
    def test_start_scheduler_registers_facebook_reels_jobs_when_enabled(self, mock_scheduler_class):
        scheduler_instance = Mock()
        mock_scheduler_class.return_value = scheduler_instance

        with self.settings(
            FACEBOOK_REELS_ENABLED=True,
            FACEBOOK_REELS_RUN_ON_STARTUP=True,
            FACEBOOK_REELS_DAILY_HOUR=11,
            FACEBOOK_REELS_DAILY_MINUTE=15,
            X_POST_ENABLED=False,
            B2_AUTO_SYNC_ENABLED=False,
            IMAGE_INTEGRITY_CHECK_ENABLED=False,
            PLAYLIST_WEEKLY_RANDOMIZE_ENABLED=False,
        ):
            core_scheduler.start_scheduler()

        scheduled_ids = [call.kwargs.get('id') for call in scheduler_instance.add_job.call_args_list]
        self.assertIn('facebook_post_job', scheduled_ids)
        self.assertIn('initial_facebook_post_job', scheduled_ids)
        self.assertIn('facebook_reels_job', scheduled_ids)
        self.assertIn('initial_facebook_reels_job', scheduled_ids)

    @patch('core.views._publish_ready_what_just_landed_reel_preview')
    @patch('core.views._generate_what_just_landed_reel_preview')
    def test_reel_pass_prefers_publishing_ready_preview_before_generating_new_one(self, mock_generate, mock_publish):
        article = BlogArticle.objects.create(
            slug='ready-preview',
            title='Artist - Ready Preview: What Just Landed',
            subtitle='Artist just landed with Ready Preview, a single release arriving on Monday 06 Apr.',
            category='Comeback',
            source_title='Comeback Signal Hub',
            source_url='https://example.com/source/ready-preview',
            source_name='K-Beats',
            image='https://example.com/ready-preview.jpg',
            image_2='',
            image_3='',
            body_html='<p>Signal copy.</p>',
            reading_time=3,
            facebook_reel_preview_video_path='generated/facebook_reels/ready-preview.mp4',
            facebook_reel_preview_status='ready',
            facebook_reel_publish_status='scheduled',
            facebook_reel_publish_scheduled_at=timezone.now() - timedelta(minutes=1),
        )
        mock_publish.return_value = {'mode': 'published', 'video_id': 'abc'}

        with self.settings(FACEBOOK_REELS_ENABLED=True):
            result = core_views._post_next_what_just_landed_facebook_reel()

        self.assertEqual(result['mode'], 'published')
        mock_publish.assert_called_once_with(article)
        mock_generate.assert_not_called()


class RadioCoIntegrationTests(TestCase):
    @patch('core.views.requests.get')
    @patch('core.views._build_live_show_snapshot')
    def test_api_live_status_uses_radioco_when_enabled(self, mock_show_snapshot, mock_get):
        cache.clear()
        RadioTrack.objects.create(
            title='Adore U',
            artist='SEVENTEEN',
            album_art='https://example.com/seventeen-adore-u.jpg',
            audio_url='https://example.com/adore-u.mp3',
            duration='3:00',
            duration_seconds=180,
        )
        mock_show_snapshot.return_value = {'current': None, 'next': None}
        station_response = Mock()
        station_response.raise_for_status.return_value = None
        station_response.json.return_value = {
            'station': {
                'listen_url': 'https://streaming.radio.co/test/listen',
                'logo': 'https://example.com/logo.jpg',
            }
        }
        track_response = Mock()
        track_response.raise_for_status.return_value = None
        track_response.json.return_value = {
            'data': {
                'title': 'Radio Song',
                'artist': 'Radio Artist',
                'artwork_urls': {'large': 'https://example.com/art.jpg'},
                'start_time': '2026-04-02T10:00:00Z',
            }
        }
        status_response = Mock()
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {
            'current_track': {'title': 'Radio Artist - Radio Song'},
            'history': [
                {'title': 'Radio Artist - Radio Song'},
                {'title': 'SEVENTEEN - Adore U'},
                {'title': 'EXO - Growl'},
                {'title': 'SHINee - View'},
                {'title': 'TAEMIN - Move'},
                {'title': 'Red Velvet - Psycho'},
                {'title': 'Broadcast Starting'},
            ],
            'logo_url': 'https://example.com/logo.jpg',
        }
        mock_get.side_effect = [station_response, track_response, status_response]

        with self.settings(
            RADIOCO_ENABLED=True,
            RADIOCO_STATION_ID='station123',
            RADIOCO_LISTEN_URL='https://streaming.radio.co/test/listen',
            RADIOCO_API_BASE='https://public.radio.co',
        ):
            response = self.client.get(reverse('api_live_status'))

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['current_track']['title'], 'Radio Song')
        self.assertEqual(payload['current_track']['artist'], 'Radio Artist')
        self.assertEqual(payload['current_track']['audio_url'], 'https://streaming.radio.co/test/listen')
        self.assertEqual(len(payload['recently_played']), 5)
        self.assertEqual(payload['recently_played'][0]['artist'], 'SEVENTEEN')
        self.assertEqual(payload['recently_played'][0]['title'], 'Adore U')
        self.assertEqual(
            payload['recently_played'][0]['album_art'],
            'https://example.com/seventeen-adore-u.jpg',
        )

    @patch('core.views.requests.get')
    @patch('core.views._build_live_show_snapshot')
    def test_live_page_context_uses_radioco_track(self, mock_show_snapshot, mock_get):
        cache.clear()
        mock_show_snapshot.return_value = {'current': None, 'next': None}
        station_response = Mock()
        station_response.raise_for_status.return_value = None
        station_response.json.return_value = {
            'station': {
                'listen_url': 'https://streaming.radio.co/test/listen',
                'logo': 'https://example.com/logo.jpg',
            }
        }
        track_response = Mock()
        track_response.raise_for_status.return_value = None
        track_response.json.return_value = {
            'data': {
                'title': 'Radio Song',
                'artist': 'Radio Artist',
                'artwork_urls': {'large': 'https://example.com/art.jpg'},
            }
        }
        status_response = Mock()
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {
            'current_track': {'title': 'Radio Artist - Radio Song'},
            'history': [
                {'title': 'NCT 127 - Fact Check'},
                {'title': 'ATEEZ - Wave'},
            ],
            'logo_url': 'https://example.com/logo.jpg',
        }
        mock_get.side_effect = [station_response, track_response, status_response]

        with self.settings(
            RADIOCO_ENABLED=True,
            RADIOCO_STATION_ID='station123',
            RADIOCO_LISTEN_URL='https://streaming.radio.co/test/listen',
            RADIOCO_API_BASE='https://public.radio.co',
        ):
            response = self.client.get(reverse('live'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Radio Song')
        self.assertContains(response, 'Fact Check')

    @patch('core.views.requests.get')
    def test_recently_played_reuses_cached_current_track_artwork(self, mock_get):
        cache.clear()
        station_response = Mock()
        station_response.raise_for_status.return_value = None
        station_response.json.return_value = {
            'data': {
                'name': 'K Beats Radio',
                'logo': 'https://example.com/logo.jpg',
                'streaming_links': [{'url': 'https://streaming.radio.co/test/listen'}],
            }
        }
        track_response = Mock()
        track_response.raise_for_status.return_value = None
        track_response.json.return_value = {
            'data': {
                'track_title': 'Monster',
                'track_artist': 'SEVENTEEN',
                'artwork_urls': {'large': 'https://example.com/monster.jpg'},
                'start_time': '2026-04-02T10:00:00Z',
            }
        }
        status_response = Mock()
        status_response.raise_for_status.return_value = None
        status_response.json.return_value = {
            'current_track': {
                'title': 'NCT DREAM - Beat It Up',
                'artwork_url_large': 'https://example.com/beat-it-up.jpg',
            },
            'history': [
                {'title': 'SEVENTEEN - Monster'},
                {'title': 'SEVENTEEN - Monster'},
            ],
            'logo_url': 'https://example.com/logo.jpg',
        }
        mock_get.side_effect = [station_response, track_response, status_response]

        with self.settings(
            RADIOCO_ENABLED=True,
            RADIOCO_STATION_ID='station123',
            RADIOCO_LISTEN_URL='https://streaming.radio.co/test/listen',
            RADIOCO_API_BASE='https://public.radio.co',
        ):
            current = core_views._radioco_current_track_namespace()
            recent = core_views._radioco_recently_played_tracks(limit=5)

        self.assertEqual(current.title, 'Monster')
        self.assertEqual(current.album_art, 'https://example.com/monster.jpg')
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].title, 'Monster')
        self.assertEqual(recent[0].album_art, 'https://example.com/monster.jpg')
