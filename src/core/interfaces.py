from abc import ABC, abstractmethod
from typing import Optional, List, Set
from src.core.models import Product

class SheetClient(ABC):
    """Interface for spreadsheet data operations (Google Sheets, Excel, Airtable, etc.)"""

    @abstractmethod
    def get_pending_product(self) -> Optional[Product]:
        pass

    @abstractmethod
    def mark_product_completed(self, product: Product) -> bool:
        pass

    @abstractmethod
    def update_instagram_post_id(self, row_index: int, post_id: str) -> bool:
        pass

    @abstractmethod
    def update_instagram_flag(self, row_index: int, flag: str = "Y") -> bool:
        pass

    @abstractmethod
    def update_whatsapp_flag(self, row_index: int, flag: str = "Y") -> bool:
        pass

    @abstractmethod
    def append_products(self, products: List[Product]) -> int:
        pass

    @abstractmethod
    def get_existing_links_or_names(self) -> Set[str]:
        pass


class ImageGenerator(ABC):
    """Interface for downloading and generating social media creatives."""

    @abstractmethod
    def download_image(self, url: str, is_direct: bool = False) -> str:
        pass

    @abstractmethod
    def generate_creative(self, product: Product, img_path: str) -> str:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass


class InstagramPublisher(ABC):
    """Interface for Instagram authentication and publishing operations."""

    @abstractmethod
    def login(self) -> bool:
        pass

    @abstractmethod
    def publish(self, image_path: str, caption: str, image_url: Optional[str] = None) -> Optional[str]:
        pass


class WhatsAppPublisher(ABC):
    """Interface for WhatsApp message broadcasting."""

    @abstractmethod
    def send_message(self, text: str) -> bool:
        pass
