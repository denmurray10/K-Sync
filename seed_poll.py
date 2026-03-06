import os
import django

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import LivePoll, LivePollOption

LivePoll.objects.all().delete()
p = LivePoll.objects.create(question='WHICH COMEBACK ARE YOU MOST EXCITED FOR?', is_active=True)
LivePollOption.objects.create(poll=p, text='ATE — Stray Kids', votes=4415)
LivePollOption.objects.create(poll=p, text='MUSE — Jimin', votes=2632)
LivePollOption.objects.create(poll=p, text='Cosmic — Red Velvet', votes=1445)
print('Poll seeded successfully!')
