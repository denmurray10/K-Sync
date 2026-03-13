import os
import django
import time
from django.utils import timezone

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import BlogArticle
from core.views import _post_to_facebook_draft

def push_all():
    print("--- Starting Batch Facebook Push ---")
    
    # Get articles that haven't been successfully posted yet
    # Or to be safe and do "all", we can just fetch all. 
    # Let's target articles that haven't been posted to avoid duplicates, 
    # unless they specify otherwise. But the user said "push all".
    # I'll fetch them in descending order of creation so the newest ones are scheduled sooner.
    articles = BlogArticle.objects.order_by('-created_at')
    
    count = articles.count()
    print(f"Total Articles Found: {count}")
    
    if count == 0:
        print("No articles found in database.")
        return

    # Gap in seconds (20 minutes)
    gap = 20 * 60
    # Start 10 minutes from now
    base_time = int(time.time()) + 600
    
    success_count = 0
    fail_count = 0
    
    for i, article in enumerate(articles):
        # Calculate schedule time for this article
        scheduled_ts = base_time + (i * gap)
        scheduled_dt = timezone.datetime.fromtimestamp(scheduled_ts, tz=timezone.utc)
        
        print(f"[{i+1}/{count}] Scheduling: {article.title[:50]}...")
        print(f"    Target Time: {scheduled_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        try:
            # Clear previous post status if any to allow fresh scheduling
            article.facebook_post_id = ''
            article.facebook_posted_at = None
            article.save(update_fields=['facebook_post_id', 'facebook_posted_at'])
            
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
