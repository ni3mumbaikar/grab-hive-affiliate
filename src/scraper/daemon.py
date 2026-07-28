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
from src.scraper.ajio import AjioScraper
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
    """Scraper Daemon orchestrating multi-platform (Amazon India & Ajio.com) deal retrieval, filtering, ranking & Google Sheet insertion."""

    def __init__(
        self,
        sheet_client: Optional[SheetClient] = None,
        amazon_scraper: Optional[AmazonScraper] = None,
        ajio_scraper: Optional[AjioScraper] = None,
        scraper: Optional[AmazonScraper] = None,  # Backward compatibility parameter
        processor: Optional[DealProcessor] = None,
    ):
        if sheet_client is None:
            validate_config()
            sheet_client = GoogleSheetClient(GOOGLE_SERVICE_ACCOUNT_JSON, SPREADSHEET_ID)

        self.sheet_client = sheet_client
        self.amazon_scraper = amazon_scraper or scraper or AmazonScraper()
        self.ajio_scraper = ajio_scraper or AjioScraper()
        self.processor = processor or DealProcessor()

    def run_once(self) -> int:
        """Executes a single cycle of multi-platform (Amazon & Ajio) scraping, filtering, and appending to Google Sheet."""
        logger.info("--- Starting Multi-Platform Deal Auto-Populator Execution Cycle ---")
        try:
            logger.info("Fetching existing product entries from Google Sheet...")
            existing_entries = self.sheet_client.get_existing_links_or_names()

            products_to_add = []

            # 1. Amazon.in Scraping & Processing
            logger.info("Scraping deal items from Amazon India...")
            amazon_deals = self.amazon_scraper.scrape_todays_deals()
            logger.info("Scraped %d raw deal items from Amazon India.", len(amazon_deals))
            if amazon_deals:
                amazon_products = self.processor.process_and_rank_deals(
                    amazon_deals, existing_entries, scraper=self.amazon_scraper, provider="Amazon"
                )
                products_to_add.extend(amazon_products)
                for p in amazon_products:
                    existing_entries.add(p.name.strip().lower())
                    existing_entries.add(p.affiliate_link.strip().lower())

            # 2. Ajio.com Scraping & Processing
            logger.info("Scraping deal items from Ajio.com...")
            ajio_deals = self.ajio_scraper.scrape_todays_deals()
            logger.info("Scraped %d raw deal items from Ajio.com.", len(ajio_deals))
            if ajio_deals:
                ajio_products = self.processor.process_and_rank_deals(
                    ajio_deals, existing_entries, scraper=self.ajio_scraper, provider="Ajio"
                )
                products_to_add.extend(ajio_products)

            if not products_to_add:
                logger.info("No new qualified deals from Amazon or Ajio to append after filtering & deduplication.")
                return 0

            appended_count = self.sheet_client.append_products(products_to_add)
            logger.info("Successfully appended %d new top deals (Multi-Platform) to Google Sheet.", appended_count)

            log_activity(
                product_name=f"Batch Append ({appended_count} Multi-Platform deals)",
                link="https://www.amazon.in/deals / https://www.ajio.com",
                status="SUCCESS",
                error_message=""
            )
            return appended_count

        except Exception as e:
            logger.error("Scraper daemon run failed: %s", e, exc_info=True)
            notify_admin_email(
                subject="Multi-Platform Scraper Daemon Failure",
                message_body=f"The deal populator service failed with error:\n\n{e}"
            )
            return 0

    def run_daemon(self, interval_hours: float = SCRAPER_INTERVAL_HOURS):
        """Runs the scraper continuously in daemon mode."""
        logger.info("Starting Multi-Platform Scraper Daemon (Interval: %.1f hours)...", interval_hours)
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
