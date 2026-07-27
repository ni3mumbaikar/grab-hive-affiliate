import logging
import time
import requests
from src.core.interfaces import WhatsAppPublisher

logger = logging.getLogger(__name__)

class WhatsAppPublisherClient(WhatsAppPublisher):
    """Client for broadcasting messages to a WhatsApp group/chat using a local WhatsApp service."""

    def __init__(self, api_url: str = None, simulate: bool = False):
        self.api_url = api_url or "http://localhost:3000/send-message"
        self.simulate = simulate

    def send_message(self, text: str) -> bool:
        if self.simulate:
            logger.info("WhatsApp: Running in SIMULATION mode. Broadcasting message to local WhatsApp service mockup.")
            logger.info("WhatsApp Message Text:\n%s\n", text)
            time.sleep(0.5)
            return True

        url = self.api_url
        payload = {"text": text}
        try:
            logger.info("WhatsApp: Sending message to local WhatsApp service at %s...", url)
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("WhatsApp: Message sent successfully through local server.")
                return True
            else:
                logger.error("WhatsApp: Failed to send message. Server returned status %d: %s", response.status_code, response.text)
                return False
        except Exception as e:
            logger.error("WhatsApp: Failed to connect or send message to local WhatsApp service: %s", e)
            return False
