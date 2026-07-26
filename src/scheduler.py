import os
import sys
import time
import logging
import argparse
from pathlib import Path
from filelock import FileLock, Timeout

# Ensure project root is in python path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import (
    validate_config, GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID, 
    INSTAGRAM_USE_OFFICIAL_API, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, INSTAGRAM_SESSION_ID,
    INSTAGRAM_BUSINESS_ACCOUNT_ID, INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_GRAPH_API_VERSION,
    WHATSAPP_API_URL, WHATSAPP_SIMULATE, CRON_INTERVAL_HOURS
)
from src.sheets.client import GoogleSheetClient
from src.image.generator import PILImageGenerator
from src.instagram import InstagramPublisherClient, InstagramGraphPublisherClient
from src.whatsapp.publisher import WhatsAppPublisherClient
from src.pipeline import Pipeline

logger = logging.getLogger("scheduler")

# Lock file path to prevent concurrent executions
LOCK_FILE = Path("logs/app.lock")

def run_pipeline():
    """Initializes and runs the pipeline once."""
    logger.info("Initializing GrabHive pipeline...")
    
    # Validate configurations
    try:
        validate_config()
    except Exception as e:
        logger.critical("Configuration validation failed: %s", e)
        sys.exit(1)

    # Initialize clients
    sheet_client = GoogleSheetClient(
        credentials_info=GOOGLE_SERVICE_ACCOUNT_JSON,
        spreadsheet_id=SPREADSHEET_ID
    )
    image_gen = PILImageGenerator()
    
    # Select Instagram Publisher based on INSTAGRAM_USE_OFFICIAL_API flag
    if INSTAGRAM_USE_OFFICIAL_API:
        simulate_insta = not (INSTAGRAM_BUSINESS_ACCOUNT_ID and INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID != "your_instagram_business_account_id")
        logger.info("Instagram: Using Official Graph API implementation (Simulate=%s)", simulate_insta)
        insta_pub = InstagramGraphPublisherClient(
            business_account_id=INSTAGRAM_BUSINESS_ACCOUNT_ID or "mock_account_id",
            access_token=INSTAGRAM_ACCESS_TOKEN or "mock_token",
            api_version=INSTAGRAM_GRAPH_API_VERSION,
            simulate=simulate_insta
        )
    else:
        simulate_insta = not (INSTAGRAM_USERNAME and (INSTAGRAM_PASSWORD or INSTAGRAM_SESSION_ID) and INSTAGRAM_USERNAME != "your_instagram_username")
        logger.info("Instagram: Using Unofficial instagrapi implementation (Simulate=%s)", simulate_insta)
        insta_pub = InstagramPublisherClient(
            username=INSTAGRAM_USERNAME or "mock_user",
            password=INSTAGRAM_PASSWORD or "mock_pass",
            session_id=INSTAGRAM_SESSION_ID,
            simulate=simulate_insta
        )
    
    simulate_whatsapp = WHATSAPP_SIMULATE
    whatsapp_pub = WhatsAppPublisherClient(
        api_url=WHATSAPP_API_URL,
        simulate=simulate_whatsapp
    )

    pipeline = Pipeline(
        sheet_client=sheet_client,
        image_gen=image_gen,
        insta_pub=insta_pub,
        whatsapp_pub=whatsapp_pub
    )

    # Run once
    logger.info("Executing pipeline run...")
    processed = pipeline.run_once()
    if processed:
        logger.info("Pipeline run finished successfully.")
    else:
        logger.info("Pipeline run finished. No pending products to process (exiting gracefully).")

def execute_with_lock(daemon_mode: bool = False):
    """Executes the pipeline protected by a file lock to prevent concurrent runs."""
    # Ensure logs folder exists for the lock file
    LOCK_FILE.parent.mkdir(exist_ok=True, parents=True)
    
    lock = FileLock(LOCK_FILE, timeout=0)
    
    try:
        with lock:
            if not daemon_mode:
                run_pipeline()
            else:
                interval_seconds = CRON_INTERVAL_HOURS * 3600
                logger.info("Starting scheduler in DAEMON mode. Running every %.1f hours.", CRON_INTERVAL_HOURS)
                while True:
                    try:
                        run_pipeline()
                    except Exception as e:
                        logger.error("Error occurred during daemon execution: %s", e)
                    
                    logger.info("Sleeping for %.1f hours (%d seconds)...", CRON_INTERVAL_HOURS, interval_seconds)
                    time.sleep(interval_seconds)
                    
    except Timeout:
        logger.warning("Another instance of GrabHive Affiliate is already running. Exiting to prevent concurrent execution.")
        sys.exit(0)
    except Exception as e:
        logger.critical("Critical scheduler error: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GrabHive Affiliate Scheduler and Pipeline runner.")
    parser.add_argument("--daemon", action="store_true", help="Run continuously as a daemon loop.")
    args = parser.parse_args()
    
    execute_with_lock(daemon_mode=args.daemon)
