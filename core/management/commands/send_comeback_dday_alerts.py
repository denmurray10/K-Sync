"""
D-1 comeback alerts: email fan-club members the day before a followed group's release.

Consent model: only users with digest_enabled=True AND digest_channel_email=True
(the same opt-in used by weekly digests) receive email. Safe with the console
email backend when SMTP is not configured.

Run manually:  python manage.py send_comeback_dday_alerts [--dry-run]
Scheduled:     daily at 09:00 UTC via core/scheduler.py (COMEBACK_DDAY_ALERTS_ENABLED)
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from core.models import ComebackData, FanClubMembership, UserProfile


class Command(BaseCommand):
    help = "Email opted-in fan-club members about tomorrow's releases from groups they follow."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print what would be sent without sending.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tomorrow = timezone.now().date() + timedelta(days=1)
        day_key = tomorrow.strftime('%Y-%m-%d')

        data_obj = ComebackData.objects.filter(year=tomorrow.year, month=tomorrow.month).first()
        releases = ((data_obj.data or {}).get(day_key, {}) or {}).get('releases', []) if data_obj else []
        if not releases:
            self.stdout.write(f'No releases on {day_key} — nothing to send.')
            return

        memberships = (
            FanClubMembership.objects
            .select_related('user', 'group')
            .filter(user__profile__digest_enabled=True, user__profile__digest_channel_email=True)
            .exclude(user__email='')
        )

        per_user = {}
        for m in memberships:
            gname = m.group.name.lower()
            for rel in releases:
                artist = str(rel.get('artist') or rel.get('name') or '').strip()
                if artist and (gname in artist.lower() or artist.lower() in gname):
                    per_user.setdefault(m.user, []).append({
                        'artist': artist,
                        'title': str(rel.get('title') or rel.get('album') or '').strip(),
                    })

        sent = 0
        for user, items in per_user.items():
            lines = '\n'.join(
                f"  • {i['artist']}" + (f" — {i['title']}" if i['title'] else '')
                for i in items
            )
            plural = 'comebacks' if len(items) > 1 else 'comeback'
            subject = f"D-1: {items[0]['artist']} comeback lands tomorrow"
            body = (
                f"Hey {user.username},\n\n"
                f"Tomorrow ({tomorrow.strftime('%A %d %B')}) brings {len(items)} {plural} "
                f"from groups you follow on K-Beats:\n\n{lines}\n\n"
                f"Full details, teasers, and the countdown:\n"
                f"https://kbeatsradio.co.uk/comeback-timeline/\n\n"
                f"Stay on beat,\nThe K-Beats Team\n\n"
                f"(You get these because comeback alerts are on in your digest settings.)"
            )
            if dry_run:
                self.stdout.write(f'[dry-run] would email {user.email}: {subject}')
            else:
                try:
                    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
                    sent += 1
                except Exception as exc:
                    self.stderr.write(f'Failed for {user.email}: {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'{day_key}: {len(releases)} release(s); {len(per_user)} matched member(s); {sent} email(s) sent.'
        ))
