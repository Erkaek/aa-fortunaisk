# fortunaisk/utils.py

import requests
import logging

logger = logging.getLogger(__name__)

def send_discord_notification(webhook_url, message):
    """
    Envoie une notification à Discord via le webhook spécifié.
    """
    payload = {
        "content": message
    }
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Discord notification: {e}")