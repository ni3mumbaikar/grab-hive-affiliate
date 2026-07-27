import pytest
from unittest.mock import MagicMock, patch
from src.core.models import ScrapedDeal, Product
from src.scraper.amazon import AmazonScraper
from src.scraper.processor import DealProcessor
from src.scraper.daemon import ScraperDaemon, SingleInstanceLock
from src.core.interfaces import SheetClient

SAMPLE_AMAZON_HTML = """
<html>
<body>
    <div class="dealTile" data-asin="B09X123456">
        <a class="dealTitle" href="/dp/B09X123456">
            <span class="a-truncate-full">Wireless Noise Cancelling Headphones</span>
        </a>
        <span class="a-price"><span class="a-offscreen">₹1,999</span></span>
        <span class="a-text-price"><span class="a-offscreen">₹4,999</span></span>
        <span class="a-badge-text">60% off</span>
        <span class="a-icon-star">4.5 out of 5 stars</span>
        <span class="a-size-small"><a class="a-link-normal">1,250 ratings</a></span>
        <img src="https://images-amazon.com/headphone.jpg" alt="Wireless Noise Cancelling Headphones"/>
    </div>
    <div class="dealTile" data-asin="B08Y999999">
        <a class="dealTitle" href="/dp/B08Y999999">
            <span class="a-truncate-full">Cheap USB Cable</span>
        </a>
        <span class="a-price"><span class="a-offscreen">₹199</span></span>
        <span class="a-text-price"><span class="a-offscreen">₹249</span></span>
        <span class="a-badge-text">20% off</span>
        <span class="a-icon-star">3.8 out of 5 stars</span>
        <span class="a-size-small"><a class="a-link-normal">120 ratings</a></span>
        <img src="https://images-amazon.com/cable.jpg" alt="Cheap USB Cable"/>
    </div>
</body>
</html>
"""

def test_amazon_scraper_html_parsing():
    scraper = AmazonScraper(base_url="https://www.amazon.in")
    deals = scraper.parse_deals_from_html(SAMPLE_AMAZON_HTML)

    assert len(deals) >= 1
    deal1 = next(d for d in deals if d.asin == "B09X123456")

    assert deal1.title == "Wireless Noise Cancelling Headphones"
    assert deal1.deal_price == 1999.0
    assert deal1.list_price == 4999.0
    assert deal1.discount_percent == 60.0
    assert deal1.rating == 4.5
    assert deal1.review_count == 1250
    assert deal1.product_url == "https://www.amazon.in/dp/B09X123456"


def test_deal_processor_filter_thresholds():
    processor = DealProcessor(
        affiliate_tag="testtag-21",
        min_discount=30.0,
        min_rating=4.3,
        min_reviews=500
    )

    good_deal = ScrapedDeal(
        asin="B09X123456",
        title="Good Earbuds",
        deal_price=1999.0,
        list_price=4999.0,
        discount_percent=60.0,
        rating=4.5,
        review_count=1200,
        image_url="https://images.com/earbuds.jpg",
        product_url="https://www.amazon.in/dp/B09X123456"
    )

    low_discount_deal = ScrapedDeal(
        asin="B011111111",
        title="Low Discount Item",
        deal_price=1800.0,
        list_price=2000.0,
        discount_percent=10.0,
        rating=4.6,
        review_count=2000,
        image_url="https://images.com/item.jpg",
        product_url="https://www.amazon.in/dp/B011111111"
    )

    low_rating_deal = ScrapedDeal(
        asin="B022222222",
        title="Low Rating Item",
        deal_price=1000.0,
        list_price=3000.0,
        discount_percent=66.0,
        rating=3.9,
        review_count=1500,
        image_url="https://images.com/item2.jpg",
        product_url="https://www.amazon.in/dp/B022222222"
    )

    low_reviews_deal = ScrapedDeal(
        asin="B033333333",
        title="Low Review Count Item",
        deal_price=1000.0,
        list_price=3000.0,
        discount_percent=66.0,
        rating=4.8,
        review_count=150,
        image_url="https://images.com/item3.jpg",
        product_url="https://www.amazon.in/dp/B033333333"
    )

    assert processor.filter_deal(good_deal) is True
    assert processor.filter_deal(low_discount_deal) is False
    assert processor.filter_deal(low_rating_deal) is False
    assert processor.filter_deal(low_reviews_deal) is False


def test_deal_processor_scoring_and_affiliate_formatting():
    processor = DealProcessor(
        affiliate_tag="grabhive-21",
        min_discount=30.0,
        min_rating=4.3,
        min_reviews=500
    )

    deal = ScrapedDeal(
        asin="B09X123456",
        title="Smart Watch",
        deal_price=2999.0,
        list_price=9999.0,
        discount_percent=70.0,
        rating=4.5,
        review_count=2500,
        image_url="https://images.com/watch.jpg",
        product_url="https://www.amazon.in/dp/B09X123456"
    )

    score = processor.calculate_score(deal)
    assert score == 98.0

    affiliate_url = processor.format_affiliate_url(deal)
    assert affiliate_url == "https://www.amazon.in/dp/B09X123456?tag=grabhive-21"


def test_deal_processor_deduplication_and_ranking():
    processor = DealProcessor(affiliate_tag="testtag-21", max_deals=2)

    deal1 = ScrapedDeal(
        asin="B09X111111", title="Deal One", deal_price=1000, list_price=2000,
        discount_percent=50, rating=4.5, review_count=1000,
        image_url="http://img1.jpg", product_url="https://www.amazon.in/dp/B09X111111"
    )
    deal2 = ScrapedDeal(
        asin="B09X222222", title="Deal Two", deal_price=1000, list_price=4000,
        discount_percent=75, rating=4.8, review_count=2000,
        image_url="http://img2.jpg", product_url="https://www.amazon.in/dp/B09X222222"
    )
    deal_duplicate = ScrapedDeal(
        asin="B09X111111", title="Deal One Duplicate", deal_price=1000, list_price=2000,
        discount_percent=50, rating=4.5, review_count=1000,
        image_url="http://img1.jpg", product_url="https://www.amazon.in/dp/B09X111111"
    )

    existing_entries = {"b09x111111"}

    products = processor.process_and_rank_deals([deal1, deal2, deal_duplicate], existing_entries)

    assert len(products) == 1
    assert products[0].name == "Deal Two"
    assert products[0].affiliate_link == "https://www.amazon.in/dp/B09X222222?tag=testtag-21"


def test_scraper_daemon_run_once():
    mock_sheet = MagicMock(spec=SheetClient)
    mock_sheet.get_existing_links_or_names.return_value = set()
    mock_sheet.append_products.return_value = 1

    mock_scraper = MagicMock(spec=AmazonScraper)
    mock_scraper.enrich_deal_details.side_effect = lambda deal: deal
    mock_scraper.scrape_todays_deals.return_value = [

        ScrapedDeal(
            asin="B09X888888",
            title="Top Deal Tablet",
            deal_price=9999.0,
            list_price=19999.0,
            discount_percent=50.0,
            rating=4.6,
            review_count=1500,
            image_url="http://img.jpg",
            product_url="https://www.amazon.in/dp/B09X888888"
        )
    ]

    daemon = ScraperDaemon(sheet_client=mock_sheet, scraper=mock_scraper)
    count = daemon.run_once()

    assert count == 1
    mock_sheet.get_existing_links_or_names.assert_called_once()
    mock_sheet.append_products.assert_called_once()
