import re
import json
import logging
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from src.core.models import ScrapedDeal
from config.settings import AMAZON_BASE_URL

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

class AmazonScraper:
    """Web scraper tailored specifically for Amazon India (amazon.in) deals."""

    def __init__(self, base_url: str = AMAZON_BASE_URL):
        self.base_url = base_url.rstrip("/")

    def fetch_deals_page_html(self, url_path: str = "/deals") -> str:
        """Fetch raw HTML from Amazon India deals page with realistic request headers."""
        target_url = f"{self.base_url}{url_path}"
        logger.info("Fetching Amazon India deals from: %s", target_url)

        headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
            "Referer": "https://www.google.com/",
            "DNT": "1"
        }

        req = urllib.request.Request(target_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode("utf-8", errors="ignore")
                logger.info("Successfully fetched %d bytes of HTML from %s", len(html), target_url)
                return html
        except Exception as e:
            logger.warning("HTTP fetch failed for %s: %s", target_url, e)
            return ""

    def parse_deal_item_dict(self, deal_dict: Dict[str, Any]) -> Optional[ScrapedDeal]:
        """Parses a structured JSON deal item (as embedded by Amazon frontend API)."""
        try:
            asin = deal_dict.get("asin") or deal_dict.get("entityId")
            if not asin or len(str(asin)) != 10:
                return None

            title = deal_dict.get("title") or deal_dict.get("dealTitle") or "Amazon Product"
            deal_price = float(deal_dict.get("dealPrice") or deal_dict.get("currentPrice") or 0.0)
            list_price = float(deal_dict.get("listPrice") or deal_dict.get("basisPrice") or deal_price)
            
            discount = float(deal_dict.get("discountPercent") or 0.0)
            if discount == 0.0 and list_price > deal_price > 0:
                discount = round(((list_price - deal_price) / list_price) * 100.0, 1)

            rating = float(deal_dict.get("rating") or deal_dict.get("avgRating") or 0.0)
            review_count = int(deal_dict.get("totalReviews") or deal_dict.get("reviewCount") or 0)
            image_url = deal_dict.get("primaryImage") or deal_dict.get("imageUrl") or ""

            product_url = f"{self.base_url}/dp/{asin}"

            return ScrapedDeal(
                asin=str(asin),
                title=str(title).strip(),
                deal_price=deal_price,
                list_price=list_price,
                discount_percent=discount,
                rating=rating,
                review_count=review_count,
                image_url=image_url,
                product_url=product_url
            )
        except Exception as e:
            logger.debug("Failed to parse JSON deal item: %s", e)
            return None

    def parse_deals_from_html(self, html: str) -> List[ScrapedDeal]:
        """Parses deal items from HTML or embedded script JSON data on amazon.in."""
        deals: List[ScrapedDeal] = []
        if not html:
            return deals

        json_matches = re.findall(r'window\.dealData\s*=\s*(\{.*?\});', html, re.DOTALL)
        for match in json_matches:
            try:
                data = json.loads(match)
                items = data.get("deals", []) or data.get("items", [])
                for item in items:
                    deal = self.parse_deal_item_dict(item)
                    if deal:
                        deals.append(deal)
            except Exception:
                continue

        soup = BeautifulSoup(html, "html.parser")
        deal_cards = soup.select("[data-deal-id], .a-cardui, .dealTile, [data-asin]")

        for card in deal_cards:
            asin = card.get("data-asin")
            if not asin:
                link = card.find("a", href=re.compile(r"/dp/([A-Z0-9]{10})"))
                if link:
                    m = re.search(r"/dp/([A-Z0-9]{10})", link["href"])
                    if m:
                        asin = m.group(1)

            if not asin or len(str(asin)) != 10:
                continue

            title_el = card.select_one(".a-truncate-full, .dealTitle, h2, img[alt]")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title and title_el and title_el.get("alt"):
                title = title_el["alt"]
            if not title:
                title = f"Amazon Product {asin}"

            deal_price = 0.0
            list_price = 0.0
            price_el = card.select_one(".a-price .a-offscreen, .dealPrice")
            if price_el:
                price_str = re.sub(r"[^\d.]", "", price_el.get_text().replace(",", ""))
                if price_str:
                    try:
                        deal_price = float(price_str)
                    except ValueError:
                        pass

            list_price_el = card.select_one(".a-text-price .a-offscreen, .basisPrice")
            if list_price_el:
                list_str = re.sub(r"[^\d.]", "", list_price_el.get_text().replace(",", ""))
                if list_str:
                    try:
                        list_price = float(list_str)
                    except ValueError:
                        pass

            if list_price == 0.0:
                list_price = deal_price

            discount = 0.0
            disc_el = card.select_one(".a-badge-text, .discountBadge")
            if disc_el:
                disc_m = re.search(r"(\d+)%", disc_el.get_text())
                if disc_m:
                    discount = float(disc_m.group(1))

            if discount == 0.0 and list_price > deal_price > 0:
                discount = round(((list_price - deal_price) / list_price) * 100.0, 1)

            rating = 0.0
            rating_el = card.select_one(".a-icon-star, .a-icon-star-small")
            if rating_el:
                r_m = re.search(r"([\d.]+)", rating_el.get_text())
                if r_m:
                    try:
                        rating = float(r_m.group(1))
                    except ValueError:
                        pass

            review_count = 0
            reviews_el = card.select_one(".a-size-small .a-link-normal")
            if reviews_el:
                rev_str = re.sub(r"\D", "", reviews_el.get_text())
                if rev_str:
                    try:
                        review_count = int(rev_str)
                    except ValueError:
                        pass

            img_el = card.select_one("img[src]")
            image_url = img_el["src"] if img_el else ""

            deal = ScrapedDeal(
                asin=str(asin),
                title=title,
                deal_price=deal_price,
                list_price=list_price,
                discount_percent=discount,
                rating=rating,
                review_count=review_count,
                image_url=image_url,
                product_url=f"{self.base_url}/dp/{asin}"
            )
            deals.append(deal)

        logger.info("Parsed %d deals from HTML content.", len(deals))
        return deals

    def enrich_deal_details(self, deal: ScrapedDeal) -> ScrapedDeal:
        """Fetch product detail page HTML to extract full title, rating, and review count."""
        target_url = f"{self.base_url}/dp/{deal.asin}"
        headers = {
            "User-Agent": USER_AGENTS[0],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
        }
        req = urllib.request.Request(target_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")

                title_el = soup.select_one("#productTitle, #title")
                if title_el:
                    t = title_el.get_text(strip=True)
                    if t:
                        deal.title = t

                rating_el = soup.select_one("#acrPopover, .a-icon-star, [data-hook='rating-out-of-text']")
                if rating_el:
                    r_m = re.search(r"([\d.]+)", rating_el.get_text())
                    if r_m:
                        try:
                            deal.rating = float(r_m.group(1))
                        except ValueError:
                            pass

                rev_el = soup.select_one("#acrCustomerReviewText, [data-hook='total-review-count']")
                if rev_el:
                    rev_digits = re.sub(r"\D", "", rev_el.get_text())
                    if rev_digits:
                        try:
                            deal.review_count = int(rev_digits)
                        except ValueError:
                            pass

                # 4. Extract High-Res Product Image
                img_el = soup.select_one("#landingImage, #imgBlkFront, #main-image")
                high_res_found = None
                if img_el:
                    if img_el.get("data-old-hires"):
                        high_res_found = img_el["data-old-hires"].strip()
                    elif img_el.get("data-a-dynamic-image"):
                        try:
                            dynamic_map = json.loads(img_el["data-a-dynamic-image"])
                            if dynamic_map:
                                sorted_urls = sorted(dynamic_map.items(), key=lambda item: item[1][0] * item[1][1], reverse=True)
                                high_res_found = sorted_urls[0][0]
                        except Exception:
                            pass
                    if not high_res_found and img_el.get("src"):
                        high_res_found = img_el["src"]

                if high_res_found:
                    deal.image_url = self.upgrade_to_high_res_image_url(high_res_found)
                elif deal.image_url:
                    deal.image_url = self.upgrade_to_high_res_image_url(deal.image_url)

                logger.info("Enriched ASIN %s: Title='%s...', Rating=%.1f, Reviews=%d, Image='%s'",
                            deal.asin, deal.title[:30], deal.rating, deal.review_count, deal.image_url)
        except Exception as e:
            logger.warning("Failed to enrich deal details for ASIN %s: %s", deal.asin, e)

        return deal

    @staticmethod
    def upgrade_to_high_res_image_url(url: str) -> str:
        """Upgrades Amazon thumbnail image URLs (e.g. ._AC_SR240,220_.) to high-resolution (._SX679_.)."""
        if not url:
            return ""
        high_res_url = re.sub(r"\._AC_[^.]+\.", "._SX679_.", url)
        high_res_url = re.sub(r"\._SR\d+,\d+_\.", "._SX679_.", high_res_url)
        return high_res_url


    def scrape_todays_deals(self, enrich_details: bool = False) -> List[ScrapedDeal]:
        """High-level method to scrape today's deals from Amazon India."""
        html = self.fetch_deals_page_html("/deals")
        deals = self.parse_deals_from_html(html)

        if enrich_details and deals:
            logger.info("Enriching %d candidate deals with product page ratings & reviews...", len(deals))
            enriched_deals = []
            for deal in deals:
                enriched = self.enrich_deal_details(deal)
                enriched_deals.append(enriched)
            return enriched_deals

        return deals


