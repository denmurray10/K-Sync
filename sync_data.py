import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.scheduler import sync_calendar_data, sync_ichart_data, generate_ranking
import logging

# Configure logging to see output
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_sync():
    logger.info("--- Starting Manual Cloud Sync ---")
    
    # 1. Sync Calendar/Comeback Data
    logger.info("1/3: Syncing Upcoming Comebacks from Kpopping...")
    sync_calendar_data()
    
    # 2. Sync Real-time iChart Rankings
    logger.info("2/3: Syncing Daily Rankings from iChart...")
    sync_ichart_data()
    
    # 3. Generate initial AI rankings for other timeframes
    logger.info("3/3: Generating AI-powered rankings for other timeframes...")
    for timeframe in ['weekly', 'monthly', 'soloists', 'groups']:
        try:
            generate_ranking(timeframe)
        except Exception as e:
            logger.error(f"Error generating {timeframe} ranking: {e}")

    logger.info("--- Cloud Sync Complete! ---")

if __name__ == "__main__":
    run_sync()
