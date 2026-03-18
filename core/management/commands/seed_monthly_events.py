from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import EventBadgeDrop, LimitedTimeEvent


class Command(BaseCommand):
    help = "Seed sample monthly events and badge drops for fan-club tier/event testing"

    def handle(self, *args, **options):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(seconds=1)

        chart_battle, _ = LimitedTimeEvent.objects.update_or_create(
            slug='monthly-chart-battle',
            defaults={
                'title': 'Monthly Chart Battle',
                'event_type': 'CHART_BATTLE',
                'description': 'Vote daily in the monthly chart battle and push your fandom to #1.',
                'starts_at': month_start,
                'ends_at': month_end,
                'is_active': True,
            },
        )

        EventBadgeDrop.objects.update_or_create(
            event=chart_battle,
            badge_name='Chart Battle Contender',
            defaults={
                'badge_type': 'EVENT',
                'rarity': 'RARE',
                'minimum_tier': 'PLUS',
                'min_votes_required': 3,
                'is_active': True,
            },
        )

        spotlight_start = month_start + timedelta(days=7)
        spotlight_end = min(month_end, spotlight_start + timedelta(days=6, hours=23, minutes=59))
        spotlight, _ = LimitedTimeEvent.objects.update_or_create(
            slug='artist-spotlight-week',
            defaults={
                'title': 'Artist Spotlight Week',
                'event_type': 'ARTIST_SPOTLIGHT',
                'description': 'Celebrate this month\'s featured artist with polls, picks, and fan activity.',
                'starts_at': spotlight_start,
                'ends_at': spotlight_end,
                'is_active': True,
            },
        )

        EventBadgeDrop.objects.update_or_create(
            event=spotlight,
            badge_name='Spotlight Collector',
            defaults={
                'badge_type': 'EVENT',
                'rarity': 'EPIC',
                'minimum_tier': 'ULTRA',
                'min_votes_required': 5,
                'is_active': True,
            },
        )

        self.stdout.write(self.style.SUCCESS('Seeded monthly events and badge drops.'))
        self.stdout.write(self.style.WARNING('Chart battle slug: monthly-chart-battle'))
        self.stdout.write(self.style.WARNING('Spotlight slug: artist-spotlight-week'))