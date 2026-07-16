import json
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional
from src.interfaces import SheetClient, ImageGenerator, InstagramPublisher, WhatsAppPublisher
from src.models import Product
from src.content.caption import generate_instagram_caption
from src.content.whatsapp_msg import generate_whatsapp_message
from src.monitoring import log_activity, notify_admin_email

logger = logging.getLogger(__name__)

class ProgressTracker:
    """Manages the local progress transaction state to protect against duplicate postings."""

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.filepath.parent.mkdir(exist_ok=True, parents=True)
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load progress state file: %s. Re-initializing empty state.", e)
        return {}

    def save(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error("Failed to save progress state file: %s", e)

    def get_progress(self, link: str) -> Dict[str, Any]:
        return self.state.get(link, {"instagram_success": False, "whatsapp_success": False})

    def update_progress(self, link: str, key: str, value: bool):
        if link not in self.state:
            self.state[link] = {
                "instagram_success": False,
                "whatsapp_success": False,
                "updated_at": time.time()
            }
        self.state[link][key] = value
        self.state[link]["updated_at"] = time.time()
        self.save()

    def clear_progress(self, link: str):
        if link in self.state:
            del self.state[link]
            self.save()


class Pipeline:
    """Orchestrates the end-to-end processing pipeline from retrieval to publishing and sheet updates."""

    def __init__(self, 
                 sheet_client: SheetClient, 
                 image_gen: ImageGenerator, 
                 insta_pub: InstagramPublisher, 
                 whatsapp_pub: WhatsAppPublisher,
                 progress_path: str = "logs/publish_progress.json"):
        self.sheet_client = sheet_client
        self.image_gen = image_gen
        self.insta_pub = insta_pub
        self.whatsapp_pub = whatsapp_pub
        self.tracker = ProgressTracker(Path(progress_path))

    def run_once(self) -> bool:
        """Executes the pipeline on the first pending product from Google Sheets.
        
        Returns:
            bool: True if a product was processed (regardless of success/failure), 
                  False if no pending products were found.
        """
        # 1. Fetch pending product
        try:
            product = self.sheet_client.get_pending_product()
        except Exception as e:
            logger.error("Pipeline: Failed to retrieve pending product from Sheet: %s", e)
            # notify_admin_email(
            #     "Sheet Client Error",
            #     f"Failed to fetch pending product from spreadsheet. Error: {e}"
            # )
            return False

        if not product:
            logger.info("Pipeline: No pending products found.")
            return False

        logger.info("Pipeline: Starting pipeline execution for '%s' (Row: %d)", product.name, product.row_index)
        
        error_occurred = False
        error_msg = ""
        link = product.affiliate_link
        
        try:
            progress = self.tracker.get_progress(link)
            
            # Form captions
            caption = generate_instagram_caption(product)
            whatsapp_text = generate_whatsapp_message(product)
            
            # --- Instagram Posting ---
            if product.insta_flag == "N" and not progress.get("instagram_success"):
                logger.info("Pipeline: Publishing to Instagram...")
                try:
                    raw_img = self.image_gen.download_image(product.affiliate_link)
                    creative_img = self.image_gen.generate_creative(product, raw_img)
                    
                    success = self.insta_pub.publish(creative_img, caption)
                    if success:
                        self.tracker.update_progress(link, "instagram_success", True)
                        logger.info("Pipeline: Instagram post successful.")
                    else:
                        error_occurred = True
                        error_msg += "Instagram publish returned False. "
                        logger.error("Pipeline: Instagram post failed.")
                except Exception as e:
                    error_occurred = True
                    error_msg += f"Instagram processing error: {e}. "
                    logger.error("Pipeline: Instagram post encountered error: %s", e)
            else:
                logger.info("Pipeline: Instagram posting skipped (already marked Y or success in local state).")
                if product.insta_flag == "Y" and not progress.get("instagram_success"):
                    self.tracker.update_progress(link, "instagram_success", True)

            # --- WhatsApp Posting ---
            if product.whatsapp_flag == "N" and not progress.get("whatsapp_success"):
                logger.info("Pipeline: Publishing to WhatsApp...")
                try:
                    success = self.whatsapp_pub.send_message(whatsapp_text)
                    if success:
                        self.tracker.update_progress(link, "whatsapp_success", True)
                        logger.info("Pipeline: WhatsApp message broadcast successful.")
                    else:
                        error_occurred = True
                        error_msg += "WhatsApp broadcast returned False. "
                        logger.error("Pipeline: WhatsApp message broadcast failed.")
                except Exception as e:
                    error_occurred = True
                    error_msg += f"WhatsApp processing error: {e}. "
                    logger.error("Pipeline: WhatsApp broadcast encountered error: %s", e)
            else:
                logger.info("Pipeline: WhatsApp broadcast skipped (already marked Y or success in local state).")
                if product.whatsapp_flag == "Y" and not progress.get("whatsapp_success"):
                    self.tracker.update_progress(link, "whatsapp_success", True)

            # --- Check Transaction Finalization ---
            final_progress = self.tracker.get_progress(link)
            if final_progress.get("instagram_success") and final_progress.get("whatsapp_success"):
                logger.info("Pipeline: Both publications verified successful. Updating Google Sheets flags to Y...")
                update_ok = self.sheet_client.mark_product_completed(product)
                if update_ok:
                    self.tracker.clear_progress(link)
                    log_activity(product.name, product.affiliate_link, "SUCCESS")
                    logger.info("Pipeline: Sheet updated successfully. Transaction finalized for '%s'.", product.name)
                else:
                    error_occurred = True
                    error_msg += "Sheet client failed to update cells to Y. "
                    log_activity(product.name, product.affiliate_link, "FAILURE", "Failed to update Google Sheet flags to Y")
                    logger.error("Pipeline: Failed to update Google Sheet to finalize transaction.")
            else:
                log_activity(product.name, product.affiliate_link, "FAILURE", error_msg)
                logger.warning(
                    "Pipeline: Transaction incomplete. Flags will remain N in Google Sheets for retry. Error: %s",
                    error_msg
                )
                # if error_occurred:
                #     notify_admin_email(
                #         "Pipeline Processing Failure",
                #         f"Failed to process product '{product.name}' at row {product.row_index}.\n"
                #         f"Affiliate Link: {product.affiliate_link}\n"
                #         f"Errors: {error_msg}"
                #     )

        except Exception as e:
            logger.error("Pipeline: Unexpected error: %s", e, exc_info=True)
            log_activity(product.name, product.affiliate_link, "FAILURE", f"Unexpected error: {e}")
            # notify_admin_email(
            #     "Pipeline Unexpected Exception",
            #     f"Unexpected exception processing product '{product.name}' (Row {product.row_index}):\n{e}"
            # )
        finally:
            # Always clean up downloaded / created image files
            self.image_gen.cleanup()

        return True
