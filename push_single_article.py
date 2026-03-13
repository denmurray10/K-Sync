import os
import django
import time
from django.utils import timezone

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import BlogArticle
from core.views import _post_to_facebook_draft

def push_latest():
    print("--- Starting Manual Facebook Push ---")
    
    # Get the latest article
    article = BlogArticle.objects.order_by('-created_at').first()
    
    if not article:
        print("No articles found in database.")
        return

    print(f"Target Article: {article.title} (ID: {article.id})")
    
    # Clear previous post status if any to allow re-pushing for test
    article.facebook_post_id = ''
    article.facebook_posted_at = None
    article.save(update_fields=['facebook_post_id', 'facebook_posted_at'])
    
    # Schedule for 10 minutes from now
    scheduled_ts = int(time.time()) + 600
    
    print(f"Pushing to Facebook (scheduled for 10 mins from now)...")
    try:
        _post_to_facebook_draft(article, scheduled_unix_ts=scheduled_ts)
        
        # Note: _post_to_facebook_draft internaly calls update() which bypasses save()
        # but for verification we refresh and check
        article.refresh_from_db()
        if article.facebook_post_id:
            print(f"SUCCESS! Facebook Post ID: {article.facebook_post_id}")
            print(f"Check 'Scheduled' content in Meta Business Suite.")
        else:
            print("FAILED: Post ID not returned. Check logs for details.")
            
    except Exception as e:
        print(f"EXCEPTION: {e}")

if __name__ == "__main__":
    push_latest()
