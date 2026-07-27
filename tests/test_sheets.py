import pytest
from unittest.mock import MagicMock
from src.core.models import Product
from src.sheets.client import GoogleSheetClient

def test_google_sheet_client_append_products():
    client_connect_mock = MagicMock()
    original_connect = GoogleSheetClient._connect
    GoogleSheetClient._connect = client_connect_mock

    try:
        sheet_client = GoogleSheetClient("dummy_credentials", "dummy_spreadsheet_id")
        mock_sheet = MagicMock()
        sheet_client.sheet = mock_sheet

        mock_sheet.row_values.return_value = [
            "Product Name", "Affiliate Link", "Rating", "Price", "Provider", "Insta Flag", "WhatsApp Flag", "Image Link"
        ]

        products = [
            Product(
                row_index=0,
                name="Test Headphones",
                affiliate_link="https://www.amazon.in/dp/B09X123456?tag=grabhive-21",
                rating="4.5",
                price="₹1,499",
                provider="Amazon",
                insta_flag="N",
                whatsapp_flag="N",
                image_url="https://images-amazon.com/test.jpg"
            )
        ]

        appended_count = sheet_client.append_products(products)
        assert appended_count == 1
        mock_sheet.append_rows.assert_called_once()

    finally:
        GoogleSheetClient._connect = original_connect


def test_google_sheet_client_get_existing_links_or_names():
    client_connect_mock = MagicMock()
    original_connect = GoogleSheetClient._connect
    GoogleSheetClient._connect = client_connect_mock

    try:
        sheet_client = GoogleSheetClient("dummy_credentials", "dummy_spreadsheet_id")
        mock_sheet = MagicMock()
        sheet_client.sheet = mock_sheet

        mock_sheet.get_all_values.return_value = [
            ["Product Name", "Affiliate Link", "Rating", "Price", "Provider", "Insta Flag", "WhatsApp Flag"],
            ["Existing Watch", "https://www.amazon.in/dp/B08Y111111?tag=grabhive-21", "4.4", "₹999", "Amazon", "Y", "Y"],
        ]

        existing_set = sheet_client.get_existing_links_or_names()

        assert "existing watch" in existing_set
        assert "b08y111111" in existing_set
        assert "https://www.amazon.in/dp/b08y111111?tag=grabhive-21" in existing_set
        assert "new watch" not in existing_set

    finally:
        GoogleSheetClient._connect = original_connect
