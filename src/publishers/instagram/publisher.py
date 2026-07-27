import os
import logging
import time
from pathlib import Path
from typing import Optional
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired, ClientLoginRequired
from instagrapi.mixins.challenge import ChallengeChoice
from src.core.interfaces import InstagramPublisher

logger = logging.getLogger(__name__)

SESSION_FILE = Path("logs/instagram_session.json")

def custom_challenge_code_handler(username: str, choice) -> str:
    print("\n" + "=" * 60)
    if choice == ChallengeChoice.SMS:
        print(f" INSTAGRAM SECURITY CHECKPOINT: SMS Code sent for user '{username}'")
    elif choice == ChallengeChoice.EMAIL:
        print(f" INSTAGRAM SECURITY CHECKPOINT: Email Code sent for user '{username}'")
    else:
        print(f" INSTAGRAM SECURITY CHECKPOINT: Code required (Choice: {choice})")
    print("=" * 60)
    
    code = input("Please enter the 6-digit verification code: ").strip()
    return code

class InstagramPublisherClient(InstagramPublisher):
    """Client for publishing media to Instagram using the instagrapi library."""

    def __init__(self, username: str, password: str, session_id: Optional[str] = None, simulate: bool = True):
        self.username = username
        self.password = password
        self.session_id = session_id
        self.simulate = simulate
        self.is_logged_in = False
        self.cl = None

    def login(self) -> bool:
        if not self.username or (not self.password and not self.session_id) or self.simulate:
            logger.info("Instagram: Running in SIMULATION mode. Simulating login for user '%s'.", self.username)
            time.sleep(0.5)
            self.is_logged_in = True
            return True

        try:
            self.cl = Client()
            self.cl.challenge_code_handler = custom_challenge_code_handler
            
            if SESSION_FILE.exists():
                logger.info("Instagram: Loading saved session from %s...", SESSION_FILE)
                try:
                    self.cl.load_settings(SESSION_FILE)
                    logger.info("Instagram: Verifying saved session validity...")
                    self.cl.user_info_v1(self.cl.user_id)
                    logger.info("Instagram: Session restored successfully and verified.")
                    self.is_logged_in = True
                    return True
                except Exception as e:
                    logger.warning("Instagram: Failed to restore session (%s). Proceeding with fresh login.", e)
                    try:
                        SESSION_FILE.unlink(missing_ok=True)
                    except Exception:
                        pass
            
            if self.session_id:
                import urllib.parse
                decoded_session_id = urllib.parse.unquote(self.session_id)
                logger.info("Instagram: Attempting login using provided Session ID...")
                try:
                    self.cl.login_by_sessionid(decoded_session_id)
                    SESSION_FILE.parent.mkdir(exist_ok=True, parents=True)
                    self.cl.dump_settings(SESSION_FILE)
                    logger.info("Instagram: Logged in via Session ID and saved settings to %s.", SESSION_FILE)
                    self.is_logged_in = True
                    return True
                except Exception as e:
                    logger.error("Instagram: Session ID login failed: %s. Falling back to credentials.", e)

            logger.info("Instagram: Performing fresh login for user '%s'...", self.username)
            self.cl.login(self.username, self.password)
            
            SESSION_FILE.parent.mkdir(exist_ok=True, parents=True)
            self.cl.dump_settings(SESSION_FILE)
            logger.info("Instagram: Logged in and saved session settings to %s.", SESSION_FILE)
            self.is_logged_in = True
            return True
            
        except Exception as e:
            logger.error("Instagram: Authentication failed: %s", e)
            self.is_logged_in = False
            return False

    def publish(self, image_path: str, caption: str, image_url: Optional[str] = None) -> Optional[str]:
        if self.simulate:
            logger.info("Instagram: [SIMULATED POST SUCCESS]")
            logger.info("Instagram Image Path: %s", image_path)
            logger.info("Instagram Caption:\n%s\n", caption)
            time.sleep(1.0)
            return "17983683849042983_simulated"

        if not self.is_logged_in:
            if not self.login():
                logger.error("Instagram: Publish aborted. Authentication failed.")
                return None

        logger.info("Instagram: Uploading photo to feed. Path: %s", image_path)
        
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                media = self.cl.photo_upload(
                    path=Path(image_path),
                    caption=caption
                )
                media_id = str(media.id)
                logger.info("Instagram: Photo published successfully! Media ID: %s", media_id)
                
                fbid_str = None
                for info_attempt in range(3):
                    try:
                        if getattr(self.cl, "user_id", None):
                            feed_info = self.cl.private_request(f"feed/user/{self.cl.user_id}/")
                            if 'items' in feed_info:
                                for item in feed_info['items']:
                                    if str(item.get('pk')) == str(media.pk) or str(item.get('id')) == str(media.id):
                                        fbid = item.get('fbid')
                                        if fbid:
                                            fbid_str = str(fbid)
                                            logger.info("Instagram: Successfully retrieved Graph API FBID from user feed: %s", fbid_str)
                                            break
                                if fbid_str:
                                    break
                    except Exception as feed_err:
                        logger.warning("Instagram: FBID retrieval from user feed failed: %s.", feed_err)

                    try:
                        info = self.cl.private_request(f"media/{media.pk}/info/")
                        if 'items' in info and len(info['items']) > 0:
                            fbid = info['items'][0].get('fbid')
                            if fbid:
                                fbid_str = str(fbid)
                                logger.info("Instagram: Successfully retrieved Graph API FBID from media/info: %s", fbid_str)
                                break
                    except Exception as e:
                        logger.warning("Instagram: FBID retrieval attempt %d failed: %s", info_attempt + 1, e)
                    time.sleep(2.0)
                
                if fbid_str:
                    return fbid_str
                
                return media_id
            except Exception as e:
                is_login_req = isinstance(e, (LoginRequired, ClientLoginRequired)) or "login_required" in str(e).lower()
                if is_login_req:
                    logger.warning("Instagram: Session expired or invalid on upload attempt %d/%d: %s", attempt + 1, max_attempts, e)
                    try:
                        SESSION_FILE.unlink(missing_ok=True)
                    except Exception:
                        pass
                    self.is_logged_in = False
                    if not self.login():
                        logger.error("Instagram: Re-authentication failed during retry.")
                        return None
                else:
                    logger.error("Instagram: Upload failed on attempt %d/%d. Error: %s", attempt + 1, max_attempts, e)
                    if attempt == max_attempts - 1:
                        return None
                    time.sleep(2.0)
                
        return None
