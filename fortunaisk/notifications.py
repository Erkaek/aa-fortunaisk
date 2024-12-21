# fortunaisk/notifications.py
"""Module pour les fonctions de notification de FortunaIsk."""

# Standard Library
import logging

# Third Party
import requests

logger = logging.getLogger(__name__)


def send_discord_webhook(message):
    """
    Envoie un message au webhook Discord configuré via le modèle LotterySettings.
    """
    from .models import (
        LotterySettings,  # Import local pour éviter les imports circulaires
    )

    settings = LotterySettings.objects.get_or_create()[0]
    if not settings.discord_webhook:
        logger.warning("Webhook Discord non configuré ou URL manquante.")
        return

    payload = {"content": message}
    try:
        response = requests.post(settings.discord_webhook, json=payload, timeout=5)
        if response.status_code not in [200, 204]:
            logger.error(
                f"Échec de l'envoi du webhook Discord. Status Code: {response.status_code}, Response: {response.text}"
            )
    except requests.exceptions.RequestException as e:
        logger.exception(f"Exception lors de l'envoi du webhook Discord: {e}")
