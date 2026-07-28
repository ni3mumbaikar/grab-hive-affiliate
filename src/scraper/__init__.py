"""Multi-Platform Deals Scraper package (Amazon India & Ajio.com)."""
from src.scraper.amazon import AmazonScraper
from src.scraper.ajio import AjioScraper
from src.scraper.processor import DealProcessor
from src.scraper.daemon import ScraperDaemon

__all__ = ["AmazonScraper", "AjioScraper", "DealProcessor", "ScraperDaemon"]
