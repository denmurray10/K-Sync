from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.db import connection
from django.core.cache import cache
from unittest.mock import Mock, patch

from core import views as core_views

from .models import (
    BlogArticle,
    ComebackData,
    KPopGroup,
    LivePoll,
    LivePollOption,
    FanClubMembership,
    LimitedTimeEvent,
    EventBadgeDrop,
    EventParticipation,
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


class RadioCoIntegrationTests(TestCase):
    @patch('core.views.requests.get')
    @patch('core.views._build_live_show_snapshot')
    def test_api_live_status_uses_radioco_when_enabled(self, mock_show_snapshot, mock_get):
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
