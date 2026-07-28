import sys
import argparse
import logging
from pathlib import Path

# Ensure root directory is on PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.scraper.daemon import ScraperDaemon, SingleInstanceLock

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="GrabHive Multi-Platform Deals Auto-Populator Service (Amazon.in & Ajio.com)"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run continuously as a daemon service."
    )
    args = parser.parse_args()

    daemon = ScraperDaemon()

    if args.daemon:
        logger.info("Launching Scraper Daemon in process manager mode...")
        daemon.run_daemon()
    else:
        logger.info("Executing single scraper run...")
        lock = SingleInstanceLock()
        if lock.acquire():
            try:
                daemon.run_once()
            finally:
                lock.release()
        else:
            logger.warning("Another scraper instance is running. Exiting.")
            sys.exit(1)

if __name__ == "__main__":
    main()
