import pytest
from unittest.mock import MagicMock, patch
from src.core.models import ScrapedDeal, Product
from src.scraper.ajio import AjioScraper
from src.scraper.amazon import AmazonScraper
from src.scraper.processor import DealProcessor
from src.scraper.daemon import ScraperDaemon
from src.core.interfaces import SheetClient

SAMPLE_AJIO_JSON = {
    "products": [
        {
            "code": "469759211005",
            "name": "Men Jolt 5 Running Shoes",
            "discountPercent": "37% off",
            "price": {"value": 3464.0},
            "wasPriceData": {"value": 5499.0},
            "averageRating": 4.5,
            "totalRatingCount": 850,
            "url": "/asics-men-jolt-5-running-shoes/p/469759211005",
            "fnlColorVariantData": {
                "brandName": "ASICS",
                "outfitPictureURL": "https://assets.ajio.com/asics_jolt.jpg"
            }
        },
        {
            "code": "703697621004",
            "name": "Girls Animal-Print Bodycon Dress",
            "discountPercent": "58% off",
            "price": {"value": 286.0},
            "wasPriceData": {"value": 681.0},
            "averageRating": 4.4,
            "totalRatingCount": 320,
            "url": "/styleconnect-girls-animal-print-bodycon-dress/p/703697621004",
            "fnlColorVariantData": {
                "brandName": "STYLECONNECT",
                "outfitPictureURL": "https://assets.ajio.com/styleconnect_dress.jpg"
            }
        }
    ]
}

def test_ajio_scraper_json_parsing():
    scraper = AjioScraper(base_url="https://www.ajio.com")
    deals = scraper.parse_deals_from_json(SAMPLE_AJIO_JSON)

    assert len(deals) == 2
    deal1 = next(d for d in deals if d.asin == "469759211005")

    assert deal1.title == "ASICS Men Jolt 5 Running Shoes"
    assert deal1.deal_price == 3464.0
    assert deal1.list_price == 5499.0
    assert deal1.discount_percent == 37.0
    assert deal1.rating == 4.5
    assert deal1.review_count == 850
    assert deal1.image_url == "https://assets.ajio.com/asics_jolt.jpg"
    assert deal1.product_url == "https://www.ajio.com/asics-men-jolt-5-running-shoes/p/469759211005"


def test_ajio_affiliate_url_formatting():
    processor = DealProcessor(
        ajio_affiliate_tag="grabhive",
        ajio_affiliate_template="https://www.ajio.com/p/{code}?tag={tag}"
    )

    deal = ScrapedDeal(
        asin="469759211005",
        title="ASICS Shoes",
        deal_price=3464.0,
        list_price=5499.0,
        discount_percent=37.0,
        rating=4.5,
        review_count=850,
        image_url="https://assets.ajio.com/asics_jolt.jpg",
        product_url="https://www.ajio.com/asics-men-jolt-5-running-shoes/p/469759211005"
    )

    affiliate_url = processor.format_affiliate_url(deal, provider="Ajio")
    assert affiliate_url == "https://www.ajio.com/p/469759211005?tag=grabhive"


def test_ajio_deal_processor_ranking_and_provider():
    processor = DealProcessor(
        ajio_affiliate_tag="grabhive",
        min_discount=30.0,
        min_rating=4.0,
        min_reviews=100
    )

    deal = ScrapedDeal(
        asin="469759211005",
        title="ASICS Men Jolt 5 Running Shoes",
        deal_price=3464.0,
        list_price=5499.0,
        discount_percent=37.0,
        rating=4.5,
        review_count=850,
        image_url="https://assets.ajio.com/asics_jolt.jpg",
        product_url="https://www.ajio.com/asics-men-jolt-5-running-shoes/p/469759211005"
    )

    products = processor.process_and_rank_deals([deal], existing_sheet_entries=set(), provider="Ajio")

    assert len(products) == 1
    p = products[0]
    assert p.provider == "Ajio"
    assert p.name == "ASICS Men Jolt 5 Running Shoes"
    assert p.price == "₹3,464"
    assert p.affiliate_link == "https://www.ajio.com/p/469759211005?tag=grabhive"


def test_multi_platform_scraper_daemon_run_once():
    mock_sheet = MagicMock(spec=SheetClient)
    mock_sheet.get_existing_links_or_names.return_value = set()
    mock_sheet.append_products.return_value = 2

    mock_amazon = MagicMock(spec=AmazonScraper)
    mock_amazon.enrich_deal_details.side_effect = lambda deal: deal
    mock_amazon.scrape_todays_deals.return_value = [
        ScrapedDeal(
            asin="B09X888888",
            title="Amazon Wireless Earbuds",
            deal_price=1999.0,
            list_price=4999.0,
            discount_percent=60.0,
            rating=4.5,
            review_count=1500,
            image_url="https://images.com/earbuds.jpg",
            product_url="https://www.amazon.in/dp/B09X888888"
        )
    ]

    mock_ajio = MagicMock(spec=AjioScraper)
    mock_ajio.enrich_deal_details.side_effect = lambda deal: deal
    mock_ajio.scrape_todays_deals.return_value = [
        ScrapedDeal(
            asin="469759211005",
            title="Ajio ASICS Shoes",
            deal_price=3464.0,
            list_price=5499.0,
            discount_percent=37.0,
            rating=4.5,
            review_count=850,
            image_url="https://assets.ajio.com/asics.jpg",
            product_url="https://www.ajio.com/p/469759211005"
        )
    ]

    daemon = ScraperDaemon(
        sheet_client=mock_sheet,
        amazon_scraper=mock_amazon,
        ajio_scraper=mock_ajio
    )
    count = daemon.run_once()

    assert count == 2
    mock_sheet.get_existing_links_or_names.assert_called_once()
    mock_sheet.append_products.assert_called_once()

    appended_products = mock_sheet.append_products.call_args[0][0]
    providers = [p.provider for p in appended_products]
    assert "Amazon" in providers
    assert "Ajio" in providers
