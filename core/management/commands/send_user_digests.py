from django.core.management.base import BaseCommand

from core.digests import send_due_user_digests


class Command(BaseCommand):
    help = 'Send due opt-in user digests (in-app and/or email) using user timezone preferences.'

    def handle(self, *args, **options):
        sent_count = send_due_user_digests()
        self.stdout.write(self.style.SUCCESS(f'Digests sent: {sent_count}'))
