# fortunaisk/utils.py
"""Utilitaires pour l'application FortunaIsk, notamment pour les notifications Discord."""

import requests
import logging
from .models import WebhookConfiguration

logger = logging.getLogger(__name__)


def send_discord_webhook(message):
    """
    Envoie un message au webhook Discord configuré.
    """
    webhook = WebhookConfiguration.objects.first()
    if not webhook or not webhook.webhook_url:
        logger.warning("Webhook Discord non configuré ou URL manquante.")
        return

    payload = {"content": message}
    try:
        response = requests.post(webhook.webhook_url, json=payload, timeout=5)
        if response.status_code not in [200, 204]:
            logger.error(f"Échec de l'envoi du webhook Discord: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du webhook Discord: {e}")
