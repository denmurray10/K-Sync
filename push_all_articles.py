import os
import django
import time

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import BlogArticle
from core.views import _post_to_facebook_draft

def push_all():
    print("--- Starting Batch Facebook Push ---")
    
    # Only target articles that don't have a facebook_post_id and haven't been posted yet
    articles = BlogArticle.objects.filter(
        facebook_post_id='',
        facebook_posted_at__isnull=True
    ).order_by('-created_at')
    
    count = articles.count()
    print(f"Total New Articles to Publish: {count}")
    
    if count == 0:
        print("No new articles found to schedule.")
        return

    # Kept for compatibility with the helper signature.
    scheduled_ts = int(time.time()) + 600
    
    success_count = 0
    fail_count = 0
    
    for i, article in enumerate(articles):
        print(f"[{i+1}/{count}] Publishing: {article.title[:50]}...")
        
        try:
            _post_to_facebook_draft(article, scheduled_unix_ts=scheduled_ts)
            
            # Refresh to verify update() worked inside _post_to_facebook_draft
            article.refresh_from_db()
            if article.facebook_post_id:
                print(f"    SUCCESS! ID: {article.facebook_post_id}")
                success_count += 1
            else:
                print(f"    FAILED: No ID returned.")
                fail_count += 1
                
        except Exception as e:
            print(f"    EXCEPTION: {e}")
            fail_count += 1
        
        # Small sleep to be polite to the local DB/API
        time.sleep(0.5)

    print(f"\n--- Batch Push Complete ---")
    print(f"Total: {count}")
    print(f"Success: {success_count}")
    print(f"Fail: {fail_count}")

if __name__ == "__main__":
    push_all()
