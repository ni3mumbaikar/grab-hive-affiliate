"""Amazon India Deals Scraper package."""
from src.scraper.amazon import AmazonScraper
from src.scraper.processor import DealProcessor
from src.scraper.daemon import ScraperDaemon

__all__ = ["AmazonScraper", "DealProcessor", "ScraperDaemon"]
