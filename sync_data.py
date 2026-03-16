import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.scheduler import sync_calendar_data, sync_ichart_data, generate_ranking
from django.core.management import call_command
import logging

# Configure logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_sync():
    logger.info("--- Starting Manual Cloud Sync ---")
    
    # 1. Sync Calendar/Comeback Data
    logger.info("1/4: Syncing Upcoming Comebacks from Kpopping...")
    sync_calendar_data()

    # 2. Sync Group/Member profile images to online Kpopping CDN URLs
    logger.info("2/4: Syncing online Kpopping profile images...")
    try:
        call_command('sync_kpopping_group_profiles', backfill_members=True)
    except Exception as e:
        logger.error(f"Error syncing Kpopping profile images: {e}")
    
    # 3. Sync Real-time iChart Rankings
    logger.info("3/4: Syncing Daily Rankings from iChart...")
    sync_ichart_data()
    
    # 4. Generate initial AI rankings for other timeframes
    logger.info("4/4: Generating AI-powered rankings for other timeframes...")
    for timeframe in ['weekly', 'monthly', 'soloists', 'groups']:
        try:
            generate_ranking(timeframe)
        except Exception as e:
            logger.error(f"Error generating {timeframe} ranking: {e}")

    logger.info("--- Cloud Sync Complete! ---")

if __name__ == "__main__":
    run_sync()
