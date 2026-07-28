import logging
from typing import List, Set, Optional, Any
from src.core.models import ScrapedDeal, Product
from config.settings import (
    AMAZON_AFFILIATE_TAG,
    AJIO_AFFILIATE_TAG,
    AJIO_AFFILIATE_TEMPLATE,
    MIN_DISCOUNT_PERCENT,
    MIN_RATING,
    MIN_REVIEWS,
    MAX_DEALS_PER_RUN,
)

logger = logging.getLogger(__name__)

class DealProcessor:
    """Processes scraped deal items: filters by criteria, deduplicates, scores, and formats affiliate links."""

    def __init__(
        self,
        affiliate_tag: str = AMAZON_AFFILIATE_TAG,
        ajio_affiliate_tag: str = AJIO_AFFILIATE_TAG,
        ajio_affiliate_template: str = AJIO_AFFILIATE_TEMPLATE,
        min_discount: float = MIN_DISCOUNT_PERCENT,
        min_rating: float = MIN_RATING,
        min_reviews: int = MIN_REVIEWS,
        max_deals: int = MAX_DEALS_PER_RUN,
    ):
        self.affiliate_tag = affiliate_tag
        self.ajio_affiliate_tag = ajio_affiliate_tag
        self.ajio_affiliate_template = ajio_affiliate_template
        self.min_discount = min_discount
        self.min_rating = min_rating
        self.min_reviews = min_reviews
        self.max_deals = max_deals

    def format_affiliate_url(self, deal: ScrapedDeal, provider: str = "Amazon") -> str:
        """Converts a product deal URL into a tagged affiliate URL based on provider."""
        provider_clean = (provider or "Amazon").strip().lower()
        if provider_clean == "ajio":
            if "{code}" in self.ajio_affiliate_template and "{tag}" in self.ajio_affiliate_template:
                return self.ajio_affiliate_template.format(code=deal.asin, tag=self.ajio_affiliate_tag)
            elif "{url}" in self.ajio_affiliate_template:
                return self.ajio_affiliate_template.format(url=deal.product_url, tag=self.ajio_affiliate_tag)
            elif "?" in deal.product_url:
                return f"{deal.product_url}&tag={self.ajio_affiliate_tag}"
            else:
                return f"{deal.product_url}?tag={self.ajio_affiliate_tag}"
        else:
            if deal.asin and len(deal.asin) == 10:
                base = f"https://www.amazon.in/dp/{deal.asin}"
            else:
                base = deal.product_url
            if "?" in base:
                return f"{base}&tag={self.affiliate_tag}"
            return f"{base}?tag={self.affiliate_tag}"

    def filter_deal(self, deal: ScrapedDeal) -> bool:
        """Checks if a scraped deal satisfies quality thresholds."""
        if deal.discount_percent < self.min_discount:
            logger.debug("Discarding deal '%s': Discount %.1f%% < %.1f%%", deal.title, deal.discount_percent, self.min_discount)
            return False
        if deal.rating < self.min_rating:
            logger.debug("Discarding deal '%s': Rating %.1f < %.1f", deal.title, deal.rating, self.min_rating)
            return False
        if deal.review_count < self.min_reviews:
            logger.debug("Discarding deal '%s': Reviews %d < %d", deal.title, deal.review_count, self.min_reviews)
            return False
        return True

    def calculate_score(self, deal: ScrapedDeal) -> float:
        """Calculates V1 deal score:
        Score = (Discount% * 0.4) + (Rating * 10) + min(Reviews / 100, 30)
        """
        discount_weight = deal.discount_percent * 0.4
        rating_weight = deal.rating * 10.0
        review_weight = min(deal.review_count / 100.0, 30.0)

        score = round(discount_weight + rating_weight + review_weight, 2)
        return score

    def process_and_rank_deals(
        self,
        raw_deals: List[ScrapedDeal],
        existing_sheet_entries: Set[str],
        scraper: Optional[Any] = None,
        provider: str = "Amazon"
    ) -> List[Product]:
        """Filters candidates by discount & deduplication FIRST, then lazily enriches matching deals with product page metadata before final rating/review filtering."""
        filtered_deals: List[ScrapedDeal] = []

        for deal in raw_deals:
            # Step 1: Pre-enrichment discount filter
            if deal.discount_percent < self.min_discount:
                logger.debug("Skipping pre-enrichment candidate (ASIN/Code: %s): Discount %.1f%% < %.1f%%",
                             deal.asin, deal.discount_percent, self.min_discount)
                continue

            # Step 2: Pre-enrichment ASIN & Link deduplication
            deal.affiliate_url = self.format_affiliate_url(deal, provider=provider)
            asin_lower = deal.asin.strip().lower()
            link_lower = deal.affiliate_url.strip().lower()

            if asin_lower in existing_sheet_entries or link_lower in existing_sheet_entries:
                logger.info("Skipping duplicate candidate product (ASIN/Code: %s)", deal.asin)
                continue

            # Step 3: Lazy Detail Enrichment (HTTP fetch product page) ONLY for matching candidates
            if scraper and hasattr(scraper, "enrich_deal_details"):
                logger.info("Qualifying candidate ASIN/Code %s (Discount %.1f%% >= %.1f%%) - Fetching product page metadata...",
                             deal.asin, deal.discount_percent, self.min_discount)
                deal = scraper.enrich_deal_details(deal)
            elif deal.image_url and hasattr(scraper, "upgrade_to_high_res_image_url"):
                deal.image_url = scraper.upgrade_to_high_res_image_url(deal.image_url)

            # Step 4: Post-enrichment title deduplication
            if deal.title and deal.title.strip().lower() in existing_sheet_entries:
                logger.info("Skipping duplicate candidate product title: '%s'", deal.title)
                continue

            # Step 5: Post-enrichment rating & review count filtering
            if not self.filter_deal(deal):
                continue

            # Step 6: Score deal
            deal.score = self.calculate_score(deal)
            filtered_deals.append(deal)

        logger.info("Total %s deals passing filters and deduplication: %d", provider, len(filtered_deals))

        filtered_deals.sort(key=lambda d: d.score, reverse=True)

        top_deals = filtered_deals[: self.max_deals]
        logger.info("Selected top %d %s deals for spreadsheet appending.", len(top_deals), provider)

        products: List[Product] = []
        for deal in top_deals:
            price_formatted = f"₹{int(deal.deal_price):,}" if deal.deal_price > 0 else "Deal Offer"
            rating_formatted = f"{deal.rating:.1f}" if deal.rating > 0 else "4.5"

            product = Product(
                row_index=0,
                name=deal.title,
                affiliate_link=deal.affiliate_url or self.format_affiliate_url(deal, provider=provider),
                rating=rating_formatted,
                price=price_formatted,
                provider=provider,
                insta_flag="N",
                whatsapp_flag="N",
                image_url=deal.image_url
            )
            products.append(product)

        return products
