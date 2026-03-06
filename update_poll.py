import os
import django
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import LivePoll
p = LivePoll.objects.filter(is_active=True).first()
if p:
    p.question = 'WHICH <span class="text-transparent [-webkit-text-stroke:1px_theme(colors.primary)]">COMEBACK</span> ARE YOU MOST EXCITED FOR?'
    p.save()
    print('Updated poll title!')
