import json
import os
from pathlib import Path
import pytest
from src.core.models import Product
from src.publishers.content.caption import generate_instagram_caption
from src.publishers.content.whatsapp_msg import generate_whatsapp_message
from src.pipeline import ProgressTracker, Pipeline
from src.core.interfaces import SheetClient, ImageGenerator, InstagramPublisher, WhatsAppPublisher


# ---------------------------------------------------------
# Test Content Generators (JIRA-31)
# ---------------------------------------------------------

def test_generate_instagram_caption():
    product = Product(
        row_index=2,
        name="Samsung Galaxy Buds",
        affiliate_link="https://amazon.in/buds",
        rating="4.6",
        price="₹3499",
        provider="Amazon",
        insta_flag="N",
        whatsapp_flag="N"
    )
    caption = generate_instagram_caption(product)
    
    assert "Deal Alert" in caption
    assert "Samsung Galaxy Buds" in caption
    assert "https://amazon.in/buds" in caption
    assert "#amazon" in caption
    assert "#deal" in caption


def test_generate_whatsapp_message():
    product = Product(
        row_index=2,
        name="Samsung Galaxy Buds",
        affiliate_link="https://amazon.in/buds",
        rating="4.6",
        price="₹3499",
        provider="Amazon",
        insta_flag="N",
        whatsapp_flag="N"
    )
    message = generate_whatsapp_message(product)
    
    assert "New Deal" in message
    assert "Samsung Galaxy Buds" in message
    assert "₹3499" in message
    assert "⭐ 4.6" in message
    assert "https://amazon.in/buds" in message

# ---------------------------------------------------------
# Test Progress Tracker (JIRA-31)
# ---------------------------------------------------------

def test_progress_tracker(tmp_path):
    progress_file = tmp_path / "publish_progress.json"
    tracker = ProgressTracker(progress_file)
    
    link = "https://example.com/item"
    
    # Init state
    prog = tracker.get_progress(link)
    assert not prog["instagram_success"]
    assert not prog["whatsapp_success"]
    
    # Update state
    tracker.update_progress(link, "instagram_success", True)
    
    # Verify file reload
    tracker_new = ProgressTracker(progress_file)
    prog_new = tracker_new.get_progress(link)
    assert prog_new["instagram_success"] is True
    assert prog_new["whatsapp_success"] is False
    
    # Clear state
    tracker.clear_progress(link)
    assert tracker.get_progress(link) == {"instagram_success": False, "whatsapp_success": False}

# ---------------------------------------------------------
# Mock Clients for E2E Pipeline Testing (JIRA-32, JIRA-33)
# ---------------------------------------------------------

class MockSheetClient(SheetClient):
    def __init__(self, product: Product):
        self.product = product
        self.marked_completed = False

    def get_pending_product(self):
        return self.product if (self.product.insta_flag == "N" or self.product.whatsapp_flag == "N") else None

    def mark_product_completed(self, product: Product):
        self.marked_completed = True
        self.product.insta_flag = "Y"
        self.product.whatsapp_flag = "Y"
        return True

    def update_instagram_post_id(self, row_index: int, post_id: str):
        self.product.instagram_post_id = post_id
        return True

    def update_instagram_flag(self, row_index: int, flag: str = "Y"):
        self.product.insta_flag = flag
        return True

    def update_whatsapp_flag(self, row_index: int, flag: str = "Y"):
        self.product.whatsapp_flag = flag
        return True

    def append_products(self, products):
        return len(products)

    def get_existing_links_or_names(self):
        return set()



class MockImageGenerator(ImageGenerator):
    def __init__(self):
        self.cleaned_up = False
        self.last_downloaded_url = None
        self.last_is_direct = None

    def download_image(self, url: str, is_direct: bool = False) -> str:
        self.last_downloaded_url = url
        self.last_is_direct = is_direct
        return "temp/downloaded.jpg"

    def generate_creative(self, product: Product, img_path: str) -> str:
        return "temp/creative.png"

    def cleanup(self) -> None:
        self.cleaned_up = True


class MockInstagramPublisher(InstagramPublisher):
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.published = False

    def login(self):
        return True

    def publish(self, image_path: str, caption: str, image_url: Optional[str] = None):
        if self.should_fail:
            return None
        self.published = True
        return "17983683849042983_mock"


class MockWhatsAppPublisher(WhatsAppPublisher):
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.message_sent = False

    def send_message(self, text: str):
        if self.should_fail:
            return False
        self.message_sent = True
        return True

# ---------------------------------------------------------
# Integration & Pipeline E2E Test Runs
# ---------------------------------------------------------

def test_pipeline_success_run(tmp_path):
    progress_file = tmp_path / "publish_progress.json"
    
    product = Product(
        row_index=2,
        name="Test Item",
        affiliate_link="https://test.link",
        rating="5.0",
        price="Free",
        provider="Mock",
        insta_flag="N",
        whatsapp_flag="N"
    )
    
    sheet = MockSheetClient(product)
    image_gen = MockImageGenerator()
    insta = MockInstagramPublisher()
    whatsapp = MockWhatsAppPublisher()
    
    pipeline = Pipeline(sheet, image_gen, insta, whatsapp, str(progress_file))
    
    # Run once
    processed = pipeline.run_once()
    assert processed is True
    
    # Assert publications succeeded
    assert insta.published is True
    assert whatsapp.message_sent is True
    assert product.instagram_post_id == "17983683849042983_mock"
    
    # Assert transaction completed and Sheet flags updated to Y
    assert sheet.marked_completed is True
    assert product.insta_flag == "Y"
    assert product.whatsapp_flag == "Y"
    
    # Check that temporary assets cleanup was called
    assert image_gen.cleaned_up is True
    
    # Check progress tracker state is empty
    tracker = ProgressTracker(progress_file)
    assert tracker.get_progress("https://test.link") == {"instagram_success": False, "whatsapp_success": False}


def test_pipeline_partial_failure_idempotent_retry(tmp_path):
    progress_file = tmp_path / "publish_progress.json"
    
    product = Product(
        row_index=3,
        name="Retry Item",
        affiliate_link="https://retry.link",
        rating="4.0",
        price="$10",
        provider="Mock",
        insta_flag="N",
        whatsapp_flag="N"
    )
    
    sheet = MockSheetClient(product)
    image_gen = MockImageGenerator()
    
    # Step 1: Instagram succeeds, WhatsApp fails
    insta = MockInstagramPublisher(should_fail=False)
    whatsapp = MockWhatsAppPublisher(should_fail=True)
    
    pipeline = Pipeline(sheet, image_gen, insta, whatsapp, str(progress_file))
    processed = pipeline.run_once()
    
    assert processed is True
    assert insta.published is True
    assert whatsapp.message_sent is False
    assert sheet.marked_completed is False  # Transaction not complete
    assert product.insta_flag == "Y"         # Marked Y in sheet immediately
    assert product.instagram_post_id == "17983683849042983_mock"
    
    # Check progress tracker recorded Instagram success but WhatsApp failure
    tracker = ProgressTracker(progress_file)
    progress_state = tracker.get_progress("https://retry.link")
    assert progress_state["instagram_success"] is True
    assert progress_state["instagram_post_id"] == "17983683849042983_mock"
    assert progress_state["whatsapp_success"] is False
    
    # Step 2: Next scheduler run (WhatsApp succeeds this time)
    insta_retry = MockInstagramPublisher(should_fail=False)  # Should not be called
    whatsapp_retry = MockWhatsAppPublisher(should_fail=False)
    
    pipeline_retry = Pipeline(sheet, image_gen, insta_retry, whatsapp_retry, str(progress_file))
    processed_retry = pipeline_retry.run_once()
    
    assert processed_retry is True
    assert insta_retry.published is False      # Skipped duplicate Instagram posting!
    assert whatsapp_retry.message_sent is True  # Sent successfully on retry
    
    # Verify final completion
    assert sheet.marked_completed is True
    assert product.insta_flag == "Y"
    assert product.whatsapp_flag == "Y"
    assert product.instagram_post_id == "17983683849042983_mock"
    
    # Log must be empty now
    tracker_final = ProgressTracker(progress_file)
    assert tracker_final.get_progress("https://retry.link") == {"instagram_success": False, "whatsapp_success": False}


def test_pipeline_with_image_url(tmp_path):
    progress_file = tmp_path / "publish_progress.json"
    
    product = Product(
        row_index=4,
        name="Direct Image Item",
        affiliate_link="https://direct.link",
        rating="5.0",
        price="$20",
        provider="Mock",
        insta_flag="N",
        whatsapp_flag="N",
        image_url="https://direct.link/image.jpg"
    )
    
    sheet = MockSheetClient(product)
    image_gen = MockImageGenerator()
    insta = MockInstagramPublisher()
    whatsapp = MockWhatsAppPublisher()
    
    pipeline = Pipeline(sheet, image_gen, insta, whatsapp, str(progress_file))
    processed = pipeline.run_once()
    
    assert processed is True
    assert image_gen.last_downloaded_url == "https://direct.link/image.jpg"
    assert image_gen.last_is_direct is True


def test_google_sheet_column_mappings():
    from unittest.mock import MagicMock
    from src.sheets.client import GoogleSheetClient
    
    # Mock self._connect in __init__
    original_connect = GoogleSheetClient._connect
    GoogleSheetClient._connect = MagicMock()
    try:
        client = GoogleSheetClient("dummy_credentials", "dummy_spreadsheet_id")
        
        # Test headers including standard variations of Instagram_post_id
        headers1 = ["Product Name", "Link", "Rating", "Cost", "Store", "Instagram", "WhatsApp", "Image Link", "Instagram_post_id"]
        mappings = client._get_column_mappings(headers1)
        assert mappings["instagram_post_id"] == 8
        
        headers2 = ["productname", "url", "rate", "price", "source", "instaflag", "waflag", "imagelink", "postid"]
        mappings2 = client._get_column_mappings(headers2)
        assert mappings2["instagram_post_id"] == 8
        
        headers3 = ["productname", "url", "rate", "price", "source", "instaflag", "waflag", "imagelink", "mediaid"]
        mappings3 = client._get_column_mappings(headers3)
        assert mappings3["instagram_post_id"] == 8

        # Test case where column is missing (should not raise exception, mapping should not contain key)
        headers_missing = ["Product Name", "Link", "Rating", "Cost", "Store", "Instagram", "WhatsApp", "Image Link"]
        mappings_missing = client._get_column_mappings(headers_missing)
        assert "instagram_post_id" not in mappings_missing

    finally:
        GoogleSheetClient._connect = original_connect

