import os
import logging
import time
from typing import Optional
import requests
from src.core.interfaces import InstagramPublisher

logger = logging.getLogger(__name__)

class InstagramGraphPublisherClient(InstagramPublisher):
    """Client for publishing media to Instagram using Meta's Official Graph API."""

    def __init__(self, 
                 business_account_id: str, 
                 access_token: str, 
                 api_version: str = "v19.0", 
                 simulate: bool = True):
        self.business_account_id = business_account_id
        self.access_token = access_token
        self.api_version = api_version
        self.simulate = simulate
        self.is_logged_in = False
        self.graph_base_url = f"https://graph.facebook.com/{self.api_version}"

    def login(self) -> bool:
        if not self.business_account_id or not self.access_token:
            logger.error("Instagram (Graph API): Missing business_account_id or access_token.")
            self.is_logged_in = False
            return False

        if self.simulate:
            logger.info("Instagram (Graph API): Running in SIMULATION mode. Simulating authentication for Account ID '%s'.", self.business_account_id)
            time.sleep(0.5)
            self.is_logged_in = True
            return True

        url = f"{self.graph_base_url}/{self.business_account_id}"
        params = {
            "fields": "id,username",
            "access_token": self.access_token
        }

        try:
            logger.info("Instagram (Graph API): Verifying credentials for Account ID '%s'...", self.business_account_id)
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("Instagram (Graph API): Authenticated successfully. Account Username: %s (ID: %s)", 
                            data.get("username", "N/A"), data.get("id"))
            else:
                logger.warning("Instagram (Graph API): Direct account verification returned status %d: %s. Proceeding anyway.", resp.status_code, resp.text)
            
            self.is_logged_in = True
            return True
        except Exception as e:
            logger.warning("Instagram (Graph API): Exception during account verification: %s. Proceeding anyway.", e)
            self.is_logged_in = True
            return True

    def publish(self, image_path: str, caption: str, image_url: Optional[str] = None) -> Optional[str]:
        if self.simulate:
            logger.info("Instagram (Graph API): [SIMULATED POST SUCCESS]")
            logger.info("Instagram Image Path: %s", image_path)
            logger.info("Instagram Image URL: %s", image_url)
            logger.info("Instagram Caption:\n%s\n", caption)
            time.sleep(1.0)
            return "17983683849042983_graph_simulated"

        if not self.is_logged_in:
            if not self.login():
                logger.error("Instagram (Graph API): Publish aborted. Authentication failed.")
                return None

        target_url = None
        if image_url and image_url.strip().startswith(("http://", "https://")):
            target_url = image_url.strip()
        elif image_path and image_path.strip().startswith(("http://", "https://")):
            target_url = image_path.strip()

        if not target_url:
            logger.error(
                "Instagram (Graph API): Publish aborted. Meta Graph API requires a publicly accessible HTTP/HTTPS image URL. Neither image_url (%s) nor image_path (%s) is a valid web URL.",
                image_url, image_path
            )
            return None

        container_url = f"{self.graph_base_url}/{self.business_account_id}/media"
        container_payload = {
            "image_url": target_url,
            "caption": caption,
            "access_token": self.access_token
        }

        logger.info("Instagram (Graph API): Creating media container for URL: %s", target_url)
        try:
            resp = requests.post(container_url, data=container_payload, timeout=30)
            if resp.status_code != 200:
                logger.error("Instagram (Graph API): Container creation failed. Status: %d, Response: %s", resp.status_code, resp.text)
                return None
            
            container_data = resp.json()
            container_id = container_data.get("id")
            if not container_id:
                logger.error("Instagram (Graph API): Container creation response missing 'id': %s", container_data)
                return None

            logger.info("Instagram (Graph API): Container created successfully. Container ID: %s", container_id)
        except Exception as e:
            logger.error("Instagram (Graph API): Exception during container creation: %s", e)
            return None

        status_url = f"{self.graph_base_url}/{container_id}"
        status_params = {
            "fields": "status_code,status",
            "access_token": self.access_token
        }

        max_polls = 10
        for poll in range(max_polls):
            try:
                logger.info("Instagram (Graph API): Checking container status (attempt %d/%d)...", poll + 1, max_polls)
                status_resp = requests.get(status_url, params=status_params, timeout=15)
                if status_resp.status_code == 200:
                    status_data = status_resp.json()
                    status_code = status_data.get("status_code", "").upper()
                    logger.info("Instagram (Graph API): Container status: %s", status_code)

                    if status_code == "FINISHED":
                        break
                    elif status_code in ("ERROR", "EXPIRED"):
                        logger.error("Instagram (Graph API): Container processing failed with status: %s (%s)", status_code, status_data)
                        return None
                time.sleep(3.0)
            except Exception as e:
                logger.warning("Instagram (Graph API): Exception while polling container status: %s", e)
                time.sleep(3.0)

        publish_url = f"{self.graph_base_url}/{self.business_account_id}/media_publish"
        publish_payload = {
            "creation_id": container_id,
            "access_token": self.access_token
        }

        logger.info("Instagram (Graph API): Publishing container ID: %s", container_id)
        try:
            resp = requests.post(publish_url, data=publish_payload, timeout=30)
            if resp.status_code == 200:
                publish_data = resp.json()
                media_id = publish_data.get("id")
                if media_id:
                    logger.info("Instagram (Graph API): Post published successfully! Media ID: %s", media_id)
                    return str(media_id)
                else:
                    logger.error("Instagram (Graph API): Publish response missing 'id': %s", publish_data)
                    return None
            else:
                response_json = {}
                try:
                    response_json = resp.json()
                except Exception:
                    pass
                
                error_data = response_json.get("error", {})
                error_code = error_data.get("code")
                error_subcode = error_data.get("error_subcode")
                error_msg = error_data.get("message", "").lower()
                user_title = error_data.get("error_user_title", "").lower()
                
                if (
                    resp.status_code == 403 or 
                    error_code == 4 or 
                    error_subcode == 2207051 or 
                    "limit" in error_msg or 
                    "block" in user_title
                ):
                    logger.warning(
                        "Instagram (Graph API): Media publish returned rate limit/block error but post may be published: %s. "
                        "Proceeding as success. Fallback Media ID set to Container ID: %s", 
                        resp.text, container_id
                    )
                    return container_id
                
                logger.error("Instagram (Graph API): Media publish failed. Status: %d, Response: %s", resp.status_code, resp.text)
                return None
        except Exception as e:
            logger.error("Instagram (Graph API): Exception during media publish: %s", e)
            return None
