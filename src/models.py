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
