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

    # Test 1: /photos with native payload
    print("\nTest 1: /photos (Native Photo Post)")
    payload1 = {
        'caption': f"TEST 1: Photo Post\n{article.title}",
        'url': article.image,
        'published': 'false',
        'scheduled_publish_time': str(scheduled_ts),
        'access_token': token,
    }
    r1 = requests.post(f'https://graph.facebook.com/v19.0/{page_id}/photos', data=payload1)
    print(f"Result 1: {r1.json()}")

if __name__ == "__main__":
    test_scheduling()
