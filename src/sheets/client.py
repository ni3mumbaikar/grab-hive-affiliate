import os
import json
import logging
import time
from typing import Optional, List, Dict, Any
import gspread
from google.oauth2.service_account import Credentials
from src.interfaces import SheetClient
from src.models import Product

logger = logging.getLogger(__name__)

class GoogleSheetClient(SheetClient):
    """Concrete implementation of SheetClient using Google Sheets API via gspread."""

    def __init__(self, credentials_info: str, spreadsheet_id: str):
        self.credentials_info = credentials_info
        self.spreadsheet_id = spreadsheet_id
        self.client: Optional[gspread.Client] = None
        self.sheet: Optional[gspread.Worksheet] = None
        
        # Connect to sheet
        self._connect()

    def _execute_with_retry(self, func, *args, max_retries: int = 3, initial_delay: float = 2.0, bypass_connect: bool = False, **kwargs):
        """Executes a gspread operation with exponential backoff on failure."""
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                # If client or sheet is disconnected, try reconnecting unless bypassed
                if not self.client and not bypass_connect:
                    self._connect()
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(
                    "Google Sheet API call failed on attempt %d/%d. Error: %s", 
                    attempt + 1, max_retries, e
                )
                if attempt == max_retries - 1:
                    logger.error("All retries failed for Google Sheet operation.")
                    raise
                time.sleep(delay)
                delay *= 2

    def _authenticate(self) -> gspread.Client:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Check if credentials_info is a file path
        if os.path.exists(self.credentials_info):
            logger.info("Authenticating with Google using service account file: %s", self.credentials_info)
            creds = Credentials.from_service_account_file(self.credentials_info, scopes=scopes)
        else:
            logger.info("Authenticating with Google using in-memory Service Account JSON string.")
            try:
                creds_dict = json.loads(self.credentials_info)
                creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
            except Exception as e:
                raise ValueError(
                    "GOOGLE_SERVICE_ACCOUNT_JSON must be a valid file path or a valid JSON string."
                ) from e
                
        return gspread.authorize(creds)

    def _connect(self):
        """Establish connection to the spreadsheet and the first worksheet."""
        def connect_ops():
            self.client = self._authenticate()
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.sheet = spreadsheet.get_worksheet(0)
            logger.info("Successfully connected to Google Sheet. Spreadsheet ID: %s", self.spreadsheet_id)

        self._execute_with_retry(connect_ops, bypass_connect=True)

    def _get_column_mappings(self, headers: List[str]) -> Dict[str, int]:
        """Dynamically maps header names to their 0-based column indices.
        
        Args:
            headers: List of string headers from row 1 of the sheet.
            
        Returns:
            Dict mapping key fields to 0-based indices.
        """
        mappings = {}
        normalized_headers = [h.lower().strip().replace("_", "").replace(" ", "") for h in headers]
        
        expected = {
            "name": ["productname", "name", "title"],
            "affiliate_link": ["productaffiliatelink", "affiliatelink", "link", "url"],
            "rating": ["rating", "rate"],
            "price": ["price", "cost"],
            "provider": ["provider", "store", "source"],
            "insta_flag": ["instaflag", "instagramflag", "insta"],
            "whatsapp_flag": ["whatsappflag", "whatsapp", "waflag"],
            "image_url": ["imagelink", "imageurl", "image", "imglink", "imgurl"],
            "instagram_post_id": ["instagrampostid", "postid", "mediaid", "instapostid", "instagram_post_id"]
        }
        
        for key, aliases in expected.items():
            found = False
            for alias in aliases:
                if alias in normalized_headers:
                    mappings[key] = normalized_headers.index(alias)
                    found = True
                    break
            if not found:
                if key not in ("image_url", "instagram_post_id"):
                    # If not found, use a fallback default based on standard position
                    logger.warning("Header matching '%s' not found. Using fallback mapping.", key)
                
        # Fill in fallbacks if any columns were not mapped
        fallbacks = {
            "name": 0,
            "affiliate_link": 1,
            "rating": 2,
            "price": 3,
            "provider": 4,
            "insta_flag": 5,
            "whatsapp_flag": 6
        }
        for key, default_idx in fallbacks.items():
            if key not in mappings:
                mappings[key] = default_idx
                
        return mappings

    def get_pending_product(self) -> Optional[Product]:
        """Find the first row where Insta flag == 'N' or Whatsapp flag == 'N'."""
        def fetch_all():
            return self.sheet.get_all_values()

        rows = self._execute_with_retry(fetch_all)
        if not rows or len(rows) < 2:
            logger.info("Sheet is empty or only contains headers.")
            return None

        headers = rows[0]
        mappings = self._get_column_mappings(headers)
        
        # Scan starting from row index 1 (which is sheet row 2)
        for idx, row in enumerate(rows[1:], start=2):
            # Pad row if it has fewer elements than mapped
            max_idx = max(mappings.values())
            if len(row) <= max_idx:
                row = row + [""] * (max_idx - len(row) + 1)
                
            insta_val = row[mappings["insta_flag"]].strip().upper()
            whatsapp_val = row[mappings["whatsapp_flag"]].strip().upper()
            
            if insta_val in ("N", "") or whatsapp_val in ("N", ""):
                img_val = None
                if "image_url" in mappings and mappings["image_url"] < len(row):
                    img_val = row[mappings["image_url"]].strip()
                    
                post_id_val = None
                if "instagram_post_id" in mappings and mappings["instagram_post_id"] < len(row):
                    post_id_val = row[mappings["instagram_post_id"]].strip()
                    
                product = Product(
                    row_index=idx,
                    name=row[mappings["name"]].strip(),
                    affiliate_link=row[mappings["affiliate_link"]].strip(),
                    rating=row[mappings["rating"]].strip(),
                    price=row[mappings["price"]].strip(),
                    provider=row[mappings["provider"]].strip(),
                    insta_flag="N" if insta_val in ("N", "") else "Y",
                    whatsapp_flag="N" if whatsapp_val in ("N", "") else "Y",
                    image_url=img_val,
                    instagram_post_id=post_id_val
                )
                logger.info("Found pending product at row %d: %s", idx, product.name)
                return product

        logger.info("No pending products found in Google Sheet.")
        return None

    def mark_product_completed(self, product: Product) -> bool:
        """Mark both Insta flag and Whatsapp flag as 'Y' in the sheet."""
        def update_flags():
            # Get headers to find indices
            headers = self.sheet.row_values(1)
            mappings = self._get_column_mappings(headers)
            
            # gspread updates use 1-based columns
            insta_col = mappings["insta_flag"] + 1
            whatsapp_col = mappings["whatsapp_flag"] + 1
            
            # Update both columns in the specific row
            self.sheet.update_cell(product.row_index, insta_col, "Y")
            self.sheet.update_cell(product.row_index, whatsapp_col, "Y")
            logger.info("Successfully updated row %d to Y for Insta and Whatsapp flags.", product.row_index)
            return True

        try:
            return self._execute_with_retry(update_flags)
        except Exception as e:
            logger.error("Failed to update flags in Google Sheet for row %d: %s", product.row_index, e)
            return False

    def update_instagram_post_id(self, row_index: int, post_id: str) -> bool:
        """Write the Instagram post ID to the spreadsheet for the specified row."""
        def do_update():
            # Get headers to find indices
            headers = self.sheet.row_values(1)
            mappings = self._get_column_mappings(headers)
            
            if "instagram_post_id" in mappings:
                col = mappings["instagram_post_id"] + 1
                self.sheet.update_cell(row_index, col, post_id)
                logger.info("Successfully updated row %d with Instagram post ID %s.", row_index, post_id)
                return True
            else:
                logger.warning("Header matching 'instagram_post_id' not found in Google Sheet. Skipping post ID write.")
                return False

        try:
            return self._execute_with_retry(do_update)
        except Exception as e:
            logger.error("Failed to update Instagram post ID in Google Sheet for row %d: %s", row_index, e)
            return False

    def update_instagram_flag(self, row_index: int, flag: str = "Y") -> bool:
        """Write the Instagram status flag to the spreadsheet for the specified row."""
        def do_update():
            # Get headers to find indices
            headers = self.sheet.row_values(1)
            mappings = self._get_column_mappings(headers)
            
            if "insta_flag" in mappings:
                col = mappings["insta_flag"] + 1
                self.sheet.update_cell(row_index, col, flag)
                logger.info("Successfully updated row %d Instagram flag to %s.", row_index, flag)
                return True
            else:
                logger.warning("Header matching 'insta_flag' not found in Google Sheet. Skipping Instagram flag write.")
                return False

        try:
            return self._execute_with_retry(do_update)
        except Exception as e:
            logger.error("Failed to update Instagram flag in Google Sheet for row %d: %s", row_index, e)
            return False

    def update_whatsapp_flag(self, row_index: int, flag: str = "Y") -> bool:
        """Write the WhatsApp status flag to the spreadsheet for the specified row."""
        def do_update():
            # Get headers to find indices
            headers = self.sheet.row_values(1)
            mappings = self._get_column_mappings(headers)
            
            if "whatsapp_flag" in mappings:
                col = mappings["whatsapp_flag"] + 1
                self.sheet.update_cell(row_index, col, flag)
                logger.info("Successfully updated row %d WhatsApp flag to %s.", row_index, flag)
                return True
            else:
                logger.warning("Header matching 'whatsapp_flag' not found in Google Sheet. Skipping WhatsApp flag write.")
                return False

        try:
            return self._execute_with_retry(do_update)
        except Exception as e:
            logger.error("Failed to update WhatsApp flag in Google Sheet for row %d: %s", row_index, e)
            return False

