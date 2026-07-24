import os
import logging
import time
from pathlib import Path
from typing import Optional
from instagrapi import Client
from instagrapi.exceptions import ClientError, LoginRequired, ClientLoginRequired
from instagrapi.mixins.challenge import ChallengeChoice
from src.interfaces import InstagramPublisher

logger = logging.getLogger(__name__)

SESSION_FILE = Path("logs/instagram_session.json")

def custom_challenge_code_handler(username: str, choice) -> str:
    """Console-based challenge handler to resolve Instagram login checkpoints (JIRA-16/18)."""
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
    """Client for publishing media to Instagram using the instagrapi library.
    
    Supports simulated (mock) runs and full production publishing with session caching.
    """

    def __init__(self, username: str, password: str, session_id: Optional[str] = None, simulate: bool = True):
        self.username = username
        self.password = password
        self.session_id = session_id
        self.simulate = simulate
        self.is_logged_in = False
        self.cl = None

    def login(self) -> bool:
        """Authenticate with Instagram using instagrapi and persist the session."""
        if not self.username or (not self.password and not self.session_id) or self.simulate:
            logger.info("Instagram: Running in SIMULATION mode. Simulating login for user '%s'.", self.username)
            time.sleep(0.5)
            self.is_logged_in = True
            return True

        try:
            self.cl = Client()
            self.cl.challenge_code_handler = custom_challenge_code_handler
            
            # Check if session file exists
            if SESSION_FILE.exists():
                logger.info("Instagram: Loading saved session from %s...", SESSION_FILE)
                try:
                    self.cl.load_settings(SESSION_FILE)
                    
                    # Verify session validity by making a lightweight request (e.g. get_timeline_feed)
                    logger.info("Instagram: Verifying saved session validity...")
                    self.cl.get_timeline_feed()
                    
                    logger.info("Instagram: Session restored successfully and verified.")
                    self.is_logged_in = True
                    return True
                except Exception as e:
                    logger.warning("Instagram: Failed to restore session (%s). Proceeding with fresh login.", e)
                    try:
                        SESSION_FILE.unlink(missing_ok=True)
                    except Exception:
                        pass
            
            # Try login by session id first if provided
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

            # Fresh login via credentials
            logger.info("Instagram: Performing fresh login for user '%s'...", self.username)
            self.cl.login(self.username, self.password)
            
            # Save session for next time
            SESSION_FILE.parent.mkdir(exist_ok=True, parents=True)
            self.cl.dump_settings(SESSION_FILE)
            logger.info("Instagram: Logged in and saved session settings to %s.", SESSION_FILE)
            self.is_logged_in = True
            return True
            
        except Exception as e:
            logger.error("Instagram: Authentication failed: %s", e)
            self.is_logged_in = False
            return False
    def publish(self, image_path: str, caption: str) -> Optional[str]:
        """Publish post image with caption to Instagram feed."""
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
        
        # JIRA-18: Retry logic
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # instagrapi expects a Path object or string path
                media = self.cl.photo_upload(
                    path=Path(image_path),
                    caption=caption
                )
                media_id = str(media.id)
                logger.info("Instagram: Photo published successfully! Media ID: %s", media_id)
                
                # Retrieve the Graph API FBID (Facebook ID) of the media
                try:
                    info = self.cl.private_request(f"media/{media.pk}/info/")
                    if 'items' in info and len(info['items']) > 0:
                        fbid = info['items'][0].get('fbid')
                        if fbid:
                            fbid_str = str(fbid)
                            logger.info("Instagram: Successfully retrieved Graph API FBID: %s", fbid_str)
                            return fbid_str
                except Exception as e:
                    logger.warning("Instagram: Failed to retrieve Graph API FBID: %s. Falling back to media.id.", e)
                
                return media_id
            except Exception as e:
                # Check if session is expired/invalid (raised explicitly as LoginRequired/ClientLoginRequired, or message contains login_required)
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
