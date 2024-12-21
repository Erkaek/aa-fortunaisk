# fortunaisk/utils.py

# Standard Library
import logging

# Third Party
import requests

logger = logging.getLogger(__name__)


def send_discord_notification_custom(webhook_url, message):
    """
    Envoie une notification à Discord via le webhook spécifié.
    """
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Échec de l'envoi de la notification Discord : {e}")
