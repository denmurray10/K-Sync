from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

from .models import (
    BlogArticle,
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
