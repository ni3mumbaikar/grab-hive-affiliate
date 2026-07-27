from dataclasses import dataclass
from typing import Optional

@dataclass
class Product:
    row_index: int  # The 1-indexed row number in the Google Sheet
    name: str
    affiliate_link: str
    rating: str
    price: str
    provider: str
    insta_flag: str = "N"
    whatsapp_flag: str = "N"
    image_url: Optional[str] = None  # Scraped or manually specified image URL
    instagram_post_id: Optional[str] = None

@dataclass
class ScrapedDeal:
    asin: str
    title: str
    deal_price: float
    list_price: float
    discount_percent: float
    rating: float
    review_count: int
    image_url: str
    product_url: str
    affiliate_url: Optional[str] = None
    score: float = 0.0
