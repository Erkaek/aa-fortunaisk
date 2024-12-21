# fortunaisk/notifications.py
"""Module pour les fonctions de notification de FortunaIsk."""

# Standard Library
import logging

# Third Party
import requests

logger = logging.getLogger(__name__)


def send_discord_webhook(message):
    """
    Envoie un message au webhook Discord configuré via le modèle WebhookConfiguration.
    """
    from .models import (
        WebhookConfiguration,  # Import local pour éviter les imports circulaires
    )

    webhook = WebhookConfiguration.objects.first()
    if not webhook or not webhook.webhook_url:
        logger.warning("Webhook Discord non configuré ou URL manquante.")
        return

    payload = {"content": message}
    try:
        response = requests.post(webhook.webhook_url, json=payload, timeout=5)
        if response.status_code not in [200, 204]:
            logger.error(
                f"Échec de l'envoi du webhook Discord. Status Code: {response.status_code}, Response: {response.text}"
            )
    except requests.exceptions.RequestException as e:
        logger.exception(f"Exception lors de l'envoi du webhook Discord: {e}")
