import os
import django
import requests
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import BlogArticle

def cleanup():
    print("--- Cleaning Up Accidental Facebook Posts ---")
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    
    # Target all articles that have a facebook_post_id and were updated recently
    # To be safe, we can just use the ones we know we just pushed.
    # In practice, let's just loop over all BlogArticles that have an ID.
    articles = BlogArticle.objects.exclude(facebook_post_id='')
    
    count = articles.count()
    print(f"Found {count} articles with Facebook IDs.")
    
    deleted = 0
    skipped = 0
    
    for article in articles:
        post_id = article.facebook_post_id
        print(f"Deleting {post_id} ({article.title[:30]}...)...", end=" ")
        
        try:
            # Delete from FB
            resp = requests.delete(f'https://graph.facebook.com/v22.0/{post_id}', params={'access_token': token})
            if resp.status_code == 200:
                print("DELETED")
                # Clear from our DB so we can re-push
                article.facebook_post_id = ''
                article.facebook_posted_at = None
                article.save(update_fields=['facebook_post_id', 'facebook_posted_at'])
                deleted += 1
            else:
                print(f"FAILED: {resp.json()}")
                skipped += 1
        except Exception as e:
            print(f"EXCEPTION: {e}")
            skipped += 1

    print(f"\nCleanup Complete: {deleted} deleted, {skipped} failed.")

if __name__ == "__main__":
    cleanup()
