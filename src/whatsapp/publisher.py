import logging
import time
import requests
from src.interfaces import WhatsAppPublisher

logger = logging.getLogger(__name__)

class WhatsAppPublisherClient(WhatsAppPublisher):
    """Client for broadcasting messages to a WhatsApp group/chat using a local WhatsApp service."""

    def __init__(self, token: str, phone_number_id: str, group_id: str, simulate: bool = False):
        self.token = token
        self.phone_number_id = phone_number_id
        self.group_id = group_id
        self.simulate = simulate

    def send_message(self, text: str) -> bool:
        """Send message with caption to local WhatsApp service on port 3000."""
        if self.simulate:
            logger.info("WhatsApp: Running in SIMULATION mode. Broadcasting message to local WhatsApp service mockup.")
            logger.info("WhatsApp Message Text:\n%s\n", text)
            time.sleep(0.5)
            return True

        url = "http://localhost:3000/send-message"
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

