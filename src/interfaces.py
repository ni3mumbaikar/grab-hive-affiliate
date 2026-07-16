from abc import ABC, abstractmethod
from typing import Optional
from src.models import Product

class SheetClient(ABC):
    """Interface for spreadsheet data operations (Google Sheets, Excel, Airtable, etc.)"""

    @abstractmethod
    def get_pending_product(self) -> Optional[Product]:
        """Find and return the first product that has not been posted to all channels.
        
        Returns:
            Optional[Product]: The pending product, or None if no products are pending.
        """
        pass

    @abstractmethod
    def mark_product_completed(self, product: Product) -> bool:
        """Mark both Insta and Whatsapp flags as completed ('Y') for the product.
        
        Args:
            product (Product): The product to mark completed.
            
        Returns:
            bool: True if the operation succeeded, False otherwise.
        """
        pass


class ImageGenerator(ABC):
    """Interface for downloading and generating social media creatives."""

    @abstractmethod
    def download_image(self, url: str) -> str:
        """Download product image to a temporary file.
        
        Args:
            url (str): The URL of the product image.
            
        Returns:
            str: Absolute path to the downloaded image.
        """
        pass

    @abstractmethod
    def generate_creative(self, product: Product, img_path: str) -> str:
        """Generate a 1080x1080 promotional post image with overlays.
        
        Args:
            product (Product): The product data.
            img_path (str): Path to the raw downloaded product image.
            
        Returns:
            str: Path to the generated 1080x1080 post creative image.
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up any temporary files generated during the process."""
        pass


class InstagramPublisher(ABC):
    """Interface for Instagram authentication and publishing operations."""

    @abstractmethod
    def login(self) -> bool:
        """Authenticate with Instagram.
        
        Returns:
            bool: True if login succeeded, False otherwise.
        """
        pass

    @abstractmethod
    def publish(self, image_path: str, caption: str) -> bool:
        """Publish an image with a caption to Instagram.
        
        Args:
            image_path (str): Path to the image creative.
            caption (str): The caption for the post.
            
        Returns:
            bool: True if publishing succeeded, False otherwise.
        """
        pass


class WhatsAppPublisher(ABC):
    """Interface for WhatsApp message broadcasting."""

    @abstractmethod
    def send_message(self, text: str) -> bool:
        """Send a message (with affiliate link) to the target chat/group.
        
        Args:
            text (str): The text content of the message.
            
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        pass
