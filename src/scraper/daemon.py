import os
import sys
import time
import logging
import argparse
from pathlib import Path
from typing import Optional

from config.settings import (
    GOOGLE_SERVICE_ACCOUNT_JSON,
    SPREADSHEET_ID,
    SCRAPER_INTERVAL_HOURS,
    validate_config,
)
from src.core.interfaces import SheetClient
from src.sheets.client import GoogleSheetClient
from src.scraper.amazon import AmazonScraper
from src.scraper.processor import DealProcessor
from src.core.monitoring import log_activity, notify_admin_email

logger = logging.getLogger(__name__)

LOCK_FILE_PATH = Path("logs/scraper.lock")

class SingleInstanceLock:
    """Cross-platform file locking mechanism to prevent concurrent scraper runs."""

    def __init__(self, lock_file: Path = LOCK_FILE_PATH):
        self.lock_file = lock_file
        self.fp = None

    def acquire(self) -> bool:
        try:
            self.lock_file.parent.mkdir(exist_ok=True, parents=True)
            if sys.platform == "win32":
                if self.lock_file.exists():
                    try:
                        self.lock_file.unlink()
                    except OSError:
                        logger.warning("Another scraper instance is already running.")
                        return False
                self.fp = open(self.lock_file, "w")
                self.fp.write(str(os.getpid()))
                self.fp.flush()
                return True
            else:
                import fcntl
                self.fp = open(self.lock_file, "w")
                fcntl.flock(self.fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.fp.write(str(os.getpid()))
                self.fp.flush()
                return True
        except IOError:
            logger.warning("Failed to acquire scraper lock. Another instance running?")
            return False

    def release(self):
        if self.fp:
            try:
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(self.fp, fcntl.LOCK_UN)
                self.fp.close()
                if self.lock_file.exists():
                    self.lock_file.unlink()
            except Exception as e:
                logger.error("Error releasing scraper lock file: %s", e)


class ScraperDaemon:
    """Scraper Daemon orchestrating Amazon India deal retrieval, filtering, ranking & Google Sheet insertion."""

    def __init__(
        self,
        sheet_client: Optional[SheetClient] = None,
        scraper: Optional[AmazonScraper] = None,
        processor: Optional[DealProcessor] = None,
    ):
        if sheet_client is None:
            validate_config()
            sheet_client = GoogleSheetClient(GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID)

        self.sheet_client = sheet_client
        self.scraper = scraper or AmazonScraper()
        self.processor = processor or DealProcessor()

    def run_once(self) -> int:
        """Executes a single cycle of scraping, filtering, and appending to Google Sheet."""
        logger.info("--- Starting Amazon.in Deal Auto-Populator Execution Cycle ---")
        try:
            logger.info("Fetching existing product entries from Google Sheet...")
            existing_entries = self.sheet_client.get_existing_links_or_names()

            raw_deals = self.scraper.scrape_todays_deals()
            logger.info("Scraped %d raw deal items from Amazon India.", len(raw_deals))

            if not raw_deals:

                logger.warning("No deals fetched from Amazon India in this run.")
                return 0

            products_to_add = self.processor.process_and_rank_deals(raw_deals, existing_entries, self.scraper)


            if not products_to_add:
                logger.info("No new qualified deals to append after filtering & deduplication.")
                return 0

            appended_count = self.sheet_client.append_products(products_to_add)
            logger.info("Successfully appended %d new top deals to Google Sheet.", appended_count)

            log_activity(
                product_name=f"Batch Append ({appended_count} Amazon.in deals)",
                link="https://www.amazon.in/deals",
                status="SUCCESS",
                error_message=""
            )
            return appended_count

        except Exception as e:
            logger.error("Scraper daemon run failed: %s", e, exc_info=True)
            notify_admin_email(
                subject="Amazon Scraper Daemon Failure",
                message_body=f"The Amazon India deal populator service failed with error:\n\n{e}"
            )
            return 0

    def run_daemon(self, interval_hours: float = SCRAPER_INTERVAL_HOURS):
        """Runs the scraper continuously in daemon mode."""
        logger.info("Starting Amazon Scraper Daemon (Interval: %.1f hours)...", interval_hours)
        interval_seconds = interval_hours * 3600

        while True:
            lock = SingleInstanceLock()
            if lock.acquire():
                try:
                    self.run_once()
                finally:
                    lock.release()
            else:
                logger.warning("Skipping current loop iteration because scraper lock could not be acquired.")

            logger.info("Sleeping for %.1f hours until next scraper run...", interval_hours)
            time.sleep(interval_seconds)
