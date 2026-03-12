from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
import json
import logging
import re
from core.models import Ranking
from core.views import _chat, _do_blog_generate
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

def fetch_album_art(artist, track):
    query = urllib.parse.quote(f"{artist} {track}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data['resultCount'] > 0:
                # Get the 100x100 artwork and change it to 600x600 for high-res
                artwork_url = data['results'][0]['artworkUrl100']
                return artwork_url.replace('100x100bb', '600x600bb')
    except Exception as e:
        logger.error(f"Error fetching album art for {artist} - {track}: {e}")
    return None

def generate_ranking(timeframe):
    """
    Background job to generate the K-Pop ranking and save to the DB for a specific timeframe.
    """
    logger.info(f"Starting scheduled {timeframe} K-Pop ranking generation...")
    today = timezone.now().date()
    
    # Check if we already have a ranking for today and this timeframe to prevent duplicates
    if Ranking.objects.filter(date=today, timeframe=timeframe).exists():
        logger.info(f"Ranking for {today} ({timeframe}) already exists. Skipping generation.")
        return

    if timeframe == 'soloists':
        prompt = (
            "Generate a definitive K-Pop power ranking of the Top 20 Solo Artists active right now. "
            "Consider digital sales, streaming, brand reputation, and recent social media buzz. "
            "Return the ranking as ONLY a valid JSON array of objects. "
            "Each object MUST have: 'rank' (int), 'artist' (string), 'track' (string, put 'N/A' or their latest hit), "
            "'primary_metric_support' (string), and 'trend' (string)."
        )
    elif timeframe == 'groups':
        prompt = (
            "Generate a definitive K-Pop power ranking of the Top 20 K-Pop Groups leading the industry right now. "
            "Consider album sales, world tour impact, digital dominance, and fandom size. "
            "Return the ranking as ONLY a valid JSON array of objects. "
            "Each object MUST have: 'rank' (int), 'artist' (string), 'track' (string, put 'N/A' or their latest comeback), "
            "'primary_metric_support' (string), and 'trend' (string)."
        )
    else:
        timeframe_text = {
            'daily': 'for today',
            'weekly': 'over the past 7 days',
            'monthly': 'over the past 30 days',
            'quarterly': 'over the past 90 days'
        }.get(timeframe, 'over the past 7 days')

        prompt = (
            f"Generate a definitive K-Pop power ranking of the Top 20 tracks {timeframe_text}. "
            "Synthesize high-velocity data from three pillars: "
            "1. Digital Impact (Streaming - 50% Weight): Circle Chart (Digital), MelOn Top 100, Spotify Daily Top Songs South Korea, YouTube Music. "
            "2. Music Show Wins (20% Weight): M Countdown, Music Bank, Inkigayo. "
            "3. Global Fandom (Voting/Sales - 30% Weight): Mubeat, Idol Champ, Tenasia for voting. Hanteo and Circle Chart for sales. "
            "Apply a 'Heat' weighting system: give bonuses for 'Perfect All-Kill' (PAK) and Momentum (climbing +10 spots). "
            "Return the ranking as ONLY a valid JSON array of objects. "
            "Each object MUST have the following keys: "
            "'rank' (integer), 'artist' (string), 'track' (string), "
            "'primary_metric_support' (string, e.g. 'Perfect All-Kill (PAK); 4-crown music show sweep'), "
            "and 'trend' (string: '+X Position', '-X Position', or 'Stable'). "
            "Do not include any other text, markdown formatting, or explanations outside the JSON array."
        )
    
    try:
        raw_response = _chat(prompt, system="You are an expert K-Pop music industry analyst and data synthesizer. Return ONLY raw JSON.")
        
        # Robust JSON extraction
        json_match = re.search(r'\[\s*\{.*\}\s*\]', raw_response, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            ranking_data = json.loads(json_str)
            
            # Fetch album art for each track
            for item in ranking_data:
                if not item.get('artwork_url'):
                    item['artwork_url'] = fetch_album_art(item.get('artist', ''), item.get('track', ''))
                
            # Double check we have a decent sized list
            if len(ranking_data) > 0:
                Ranking.objects.update_or_create(
                    date=today,
                    timeframe=timeframe,
                    defaults={'ranking_data': ranking_data}
                )
                logger.info(f"Successfully generated and saved {len(ranking_data)} items for {timeframe} ranking for {today}.")
            else:
                logger.error(f"AI returned an empty list for {timeframe}")
        else:
            logger.error(f"Failed to find JSON array in AI response for {timeframe}: {raw_response[:200]}...")
            
    except Exception as e:
        logger.error(f"Exception during scheduled {timeframe} ranking generation: {e}")


def _fetch_from_kpopping(year, month):
    """
    Fetch raw calendar data from Kpopping API for a specific month/year.
    """
    url = f"https://kpopping.com/api/calendar?month={month}&year={year}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        logger.error(f"Error fetching Kpopping calendar for {month}/{year}: {e}")
    return None

def sync_calendar_data():
    """
    Background job to sync K-Pop calendar data for the current and next month.
    """
    from core.models import ComebackData
    now = timezone.now()
    
    # Sync Current and Next Month
    months_to_sync = [
        (now.year, now.month),
        (now.year if now.month < 12 else now.year + 1, now.month + 1 if now.month < 12 else 1)
    ]

    for year, month in months_to_sync:
        logger.info(f"Syncing K-Pop calendar data for {month}/{year}...")
        data = _fetch_from_kpopping(year, month)
        if data:
            ComebackData.objects.update_or_create(
                year=year,
                month=month,
                defaults={'data': data}
            )
            logger.info(f"Successfully synced calendar data for {month}/{year}.")


def sync_ichart_data():
    """
    Scrape real-time rankings from iChart.kr and update the daily Ranking model.
    """
    logger.info("Starting iChart rankings sync...")
    url = "https://www.ichart.kr/rank"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
            import re
            items = []
            # Find entries: <a class="flex w-full gap-3 ...">
            entries = re.findall(r'<a[^>]+flex[^>]+w-full[^>]+gap-3[^>]*>(.*?)</a>', html, re.DOTALL)
            
            for i, entry in enumerate(entries[:20]):
                title_match = re.search(r'<h3[^>]*>(.*?)</h3>', entry)
                # Cleanup title: remove HTML tags if any
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else None
                
                artist_match = re.search(r'<p[^>]*>(.*?)</p>', entry)
                artist = re.sub(r'<[^>]+>', '', artist_match.group(1)).strip() if artist_match else None
                
                img_match = re.search(r'<img[^>]+src=["\'](.*?)["\']', entry)
                img = img_match.group(1) if img_match else None
                
                if title and artist:
                    # Fetch high-res artwork from iTunes for better quality
                    high_res_img = fetch_album_art(artist, title)
                    final_img = high_res_img if high_res_img else img
                    
                    items.append({
                        'rank': i + 1,
                        'track': title,
                        'artist': artist,
                        'artwork_url': final_img,
                        'trend': 'Stable',
                        'primary_metric_support': 'iChart Real-time Rank'
                    })
            
            if items:
                today = timezone.now().date()
                Ranking.objects.update_or_create(
                    date=today,
                    timeframe='daily',
                    defaults={'ranking_data': items}
                )
                logger.info(f"Successfully synced {len(items)} items from iChart.")
            else:
                logger.warning("No iChart items found during sync.")
                
    except Exception as e:
        logger.error(f"Error syncing iChart data: {e}")

def auto_blog_generate():
    """Background job: fetch RSS feeds and auto-generate new blog articles."""
    logger.info("[scheduler] Starting auto blog generation...")
    try:
        created = _do_blog_generate()
        logger.info("[scheduler] Auto blog generation done — %d article(s) created.", created)
    except Exception as e:
        logger.error("[scheduler] Auto blog generation failed: %s", e)


def start_scheduler():
    scheduler = BackgroundScheduler()
    # Schedule Daily: Run every day at 08:00 AM
    scheduler.add_job(generate_ranking, 'cron', args=['daily'], hour=8, minute=0, id='daily_kpop_ranking', replace_existing=True)
    
    # Schedule Weekly: Run every day at 08:00 AM
    scheduler.add_job(generate_ranking, 'cron', args=['weekly'], hour=8, minute=0, id='weekly_kpop_ranking', replace_existing=True)
    
    # Schedule Monthly: Run every day at 08:00 AM
    scheduler.add_job(generate_ranking, 'cron', args=['monthly'], hour=8, minute=0, id='monthly_kpop_ranking', replace_existing=True)
    
    # Schedule Quarterly: Run every day at 08:00 AM
    scheduler.add_job(generate_ranking, 'cron', args=['quarterly'], hour=8, minute=0, id='quarterly_kpop_ranking', replace_existing=True)
    
    # Schedule Soloists: Run every day at 08:30 AM
    scheduler.add_job(generate_ranking, 'cron', args=['soloists'], hour=8, minute=30, id='soloists_kpop_ranking', replace_existing=True)
    
    # Schedule Groups: Run every day at 08:30 AM
    scheduler.add_job(generate_ranking, 'cron', args=['groups'], hour=8, minute=30, id='groups_kpop_ranking', replace_existing=True)
    
    # Schedule iChart Sync: Run every hour
    scheduler.add_job(sync_ichart_data, 'interval', hours=1, id='sync_ichart_data', replace_existing=True)
    
    # Schedule Calendar Sync: Run every 6 hours
    scheduler.add_job(sync_calendar_data, 'interval', hours=6, id='sync_calendar_data', replace_existing=True)

    # Schedule Blog Auto-Generation: Run every 30 minutes
    scheduler.add_job(auto_blog_generate, 'interval', minutes=30, id='auto_blog_generate', replace_existing=True)

    scheduler.add_job(generate_ranking, 'date', args=['daily'], run_date=timezone.now(), id='initial_daily_sync')
    scheduler.add_job(generate_ranking, 'date', args=['soloists'], run_date=timezone.now(), id='initial_soloists_sync')
    scheduler.add_job(generate_ranking, 'date', args=['groups'], run_date=timezone.now(), id='initial_groups_sync')

    scheduler.start()
    logger.info("Scheduler started successfully for rankings and calendar sync.")
