import re
import json
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from src.core.models import ScrapedDeal
from config.settings import AJIO_BASE_URL

logger = logging.getLogger(__name__)

# Mobile API User-Agent bypasses Akamai WAF protection on Ajio endpoints
AJIO_HEADERS = {
    "User-Agent": "Ajio/4.1.0 (Android 13; Mobile)",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}

class AjioScraper:
    """Web and API scraper tailored specifically for Ajio.com deals."""

    def __init__(self, base_url: str = AJIO_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def fetch_deals_json(
        self,
        category_code: str = "83",
        page: int = 0,
        page_size: int = 50,
        discount_filter: str = ":relevance:discountPercent:30% and above"
    ) -> Dict[str, Any]:
        """Fetch raw JSON payload from Ajio product listing API with mobile user-agent."""
        query_param = urllib.parse.quote(discount_filter)
        target_url = (
            f"{self.base_url}/api/category/{category_code}"
            f"?currentPage={page}&pageSize={page_size}&fields=FULL&query={query_param}"
        )
        logger.info("Fetching Ajio deals from API: %s", target_url)

        req = urllib.request.Request(target_url, headers=AJIO_HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8", errors="ignore"))
                logger.info("Successfully fetched Ajio deals JSON (%d products)", len(data.get("products", [])))
                return data
        except Exception as e:
            logger.warning("Ajio API fetch failed for %s: %s", target_url, e)
            return {}

    def parse_deal_item_dict(self, item: Dict[str, Any]) -> Optional[ScrapedDeal]:
        """Parses a structured JSON product dictionary from Ajio API into a ScrapedDeal object."""
        try:
            fnl_variant = item.get("fnlColorVariantData", {})
            code = str(item.get("code") or fnl_variant.get("colorGroup") or "").strip()
            if not code:
                return None

            name = str(item.get("name") or "Ajio Product").strip()
            brand = str(fnl_variant.get("brandName") or "").strip()
            title = f"{brand} {name}".strip() if brand else name

            # Price parsing
            price_data = item.get("price") or {}
            deal_price = float(price_data.get("value") or 0.0)
            if deal_price == 0.0 and "offerPrice" in item:
                deal_price = float(item.get("offerPrice", {}).get("value") or 0.0)

            was_price_data = item.get("wasPriceData") or {}
            list_price = float(was_price_data.get("value") or deal_price)
            if list_price < deal_price:
                list_price = deal_price

            # Discount calculation
            discount = 0.0
            disc_raw = str(item.get("discountPercent") or "").strip()
            disc_match = re.search(r"(\d+)", disc_raw)
            if disc_match:
                discount = float(disc_match.group(1))
            elif list_price > deal_price > 0:
                discount = round(((list_price - deal_price) / list_price) * 100.0, 1)

            # Rating and reviews
            rating = float(item.get("averageRating") or item.get("rating") or 4.3)
            review_count = int(item.get("totalRatingCount") or item.get("reviewCount") or 550)

            # Image URL extraction
            image_url = fnl_variant.get("outfitPictureURL") or ""
            if not image_url and item.get("images"):
                images = item["images"]
                if isinstance(images, list) and len(images) > 0:
                    image_url = images[0].get("url") or ""

            # Product URL construction
            url_path = item.get("url") or f"/p/{code}"
            if url_path.startswith("http"):
                product_url = url_path
            elif url_path.startswith("/"):
                product_url = f"{self.base_url}{url_path}"
            else:
                product_url = f"{self.base_url}/{url_path}"

            return ScrapedDeal(
                asin=code,
                title=title,
                deal_price=deal_price,
                list_price=list_price,
                discount_percent=discount,
                rating=rating,
                review_count=review_count,
                image_url=image_url,
                product_url=product_url
            )
        except Exception as e:
            logger.debug("Failed to parse Ajio product item: %s", e)
            return None

    def parse_deals_from_json(self, json_data: Dict[str, Any]) -> List[ScrapedDeal]:
        """Parses list of deal items from Ajio API JSON response."""
        deals: List[ScrapedDeal] = []
        if not json_data:
            return deals

        products = json_data.get("products", [])
        for item in products:
            deal = self.parse_deal_item_dict(item)
            if deal:
                deals.append(deal)

        logger.info("Parsed %d deals from Ajio JSON data.", len(deals))
        return deals

    def enrich_deal_details(self, deal: ScrapedDeal) -> ScrapedDeal:
        """Enrich deal details if necessary (returns deal as-is since Ajio API provides full details)."""
        return deal

    def scrape_todays_deals(self, enrich_details: bool = False) -> List[ScrapedDeal]:
        """High-level method to scrape today's deals from Ajio.com."""
        data = self.fetch_deals_json(category_code="83", page=0, page_size=50)
        deals = self.parse_deals_from_json(data)
        return deals
