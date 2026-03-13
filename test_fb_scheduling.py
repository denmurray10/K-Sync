import os
import django
import requests
import time
from django.conf import settings
from django.utils import timezone

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import BlogArticle

def test_scheduling():
    print("--- Testing Facebook Scheduling Parameters ---")
    page_id = settings.FACEBOOK_PAGE_ID
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    
    article = BlogArticle.objects.order_by('-created_at').first()
    if not article:
        print("No articles found.")
        return

    # Try different parameter combinations
    scheduled_ts = int(time.time()) + 3600 # 1 hour from now
    
    # Test 1: /feed with published=false (capitalized string)
    print("\nTest 1: /feed with published='false'")
    payload1 = {
        'message': f"TEST 1: Feed Published=False\n{article.title}",
        'link': article.image,
        'published': 'false',
        'scheduled_publish_time': str(scheduled_ts),
        'access_token': token,
    }
    r1 = requests.post(f'https://graph.facebook.com/v19.0/{page_id}/feed', data=payload1)
    print(f"Result 1: {r1.json()}")

    # Test 2: /feed with is_published=false
    print("\nTest 2: /feed with is_published='false'")
    payload2 = {
        'message': f"TEST 2: Feed Is_Published=False\n{article.title}",
        'link': article.image,
        'is_published': 'false',
        'scheduled_publish_time': str(scheduled_ts + 60),
        'access_token': token,
    }
    r2 = requests.post(f'https://graph.facebook.com/v19.0/{page_id}/feed', data=payload2)
    print(f"Result 2: {r2.json()}")

if __name__ == "__main__":
    test_scheduling()
