import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import Ranking

r = Ranking.objects.filter(timeframe='daily').first()
if r:
    print(f"Ranking items: {len(r.ranking_data)}")
    for i, item in enumerate(r.ranking_data):
        print(f"{i+1}. {item.get('track')} - {item.get('artist')}")
else:
    print("No ranking found")
