# fortunaisk/notifications.py

# Standard Library
import logging
from datetime import datetime

# Third Party
import requests

# Django
from django.core.cache import cache
from django.db.models import QuerySet

# Alliance Auth
# AllianceAuth notifications
from allianceauth.notifications import notify as alliance_notify

# AllianceAuth Discord service (for DMs)
try:
    # Alliance Auth
    from allianceauth.services.modules.discord import DiscordBotService

    discord_service = DiscordBotService()
except ImportError:
    discord_service = None

# fortunaisk
# fortunaisk models
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)

# Discord embed colors by level
LEVEL_COLORS = {
    "info": 0x3498DB,  # blue
    "success": 0x2ECC71,  # green
    "warning": 0xF1C40F,  # yellow
    "error": 0xE74C3C,  # red
}


def build_embed(
    title: str,
    description: str = None,
    fields: list[dict] = None,
    level: str = "info",
) -> dict:
    """
    Build a Discord embed payload with timestamp, color, optional description and fields.
    """
    embed = {
        "title": title,
        "color": LEVEL_COLORS.get(level, LEVEL_COLORS["info"]),
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Good luck to all participants! 🍀"},
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = fields
    return embed


def get_webhook_url() -> str:
    """
    Retrieve and cache the Discord webhook URL for public announcements.
    """
    url = cache.get("discord_webhook_url")
    if url is None:
        cfg = WebhookConfiguration.objects.first()
        url = cfg.webhook_url if cfg and cfg.webhook_url else ""
        cache.set("discord_webhook_url", url or "", 300)
    return url


def send_webhook_notification(embed: dict = None, content: str = None) -> bool:
    """
    Send an embed or plain content via the public Discord webhook.
    Returns True on HTTP 2xx, False otherwise.
    """
    url = get_webhook_url()
    if not url:
        logger.warning("Discord webhook not configured; skipping public notification.")
        return False

    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("Public Discord webhook message sent successfully.")
        return True
    except Exception as e:
        logger.error(
            f"Failed to send public Discord webhook message: {e}", exc_info=True
        )
        return False


def send_discord_dm(user, embed: dict = None, message: str = None) -> bool:
    """
    Attempt to send a private Discord DM via the AllianceAuth Discord bot service.
    Returns True if the message was queued, False otherwise.
    """
    if discord_service is None:
        logger.warning("Discord service not available; cannot send DM.")
        return False

    try:
        # The service takes user, embed, and/or message
        discord_service.send_message(user=user, embed=embed, message=message or "")
        logger.info(f"[Discord DM] Queued DM to {user.username}")
        return True
    except Exception as e:
        logger.error(
            f"[Discord DM] Failed to send DM to {user.username}: {e}", exc_info=True
        )
        return False


def notify_discord_or_fallback(
    users,
    *,
    title: str = None,
    message: str = None,
    embed: dict = None,
    level: str = "info",
    private: bool = False,
):
    """
    Notify one or more users.

    - If private=True:
        1) Attempt a Discord DM via the AllianceAuth Discord bot.
        2) If that fails, fallback to AllianceAuth internal notifications.
    - Else:
        1) Send a public webhook announcement (embed or message).
        2) If that fails, fallback per-user to AllianceAuth notifications.
    """
    # Build a minimal embed if only title/message provided
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    # Normalize recipients to a list
    if isinstance(users, QuerySet):
        recipients = list(users)
    elif isinstance(users, (list, tuple)):
        recipients = list(users)
    else:
        recipients = [users]

    def extract_text_from_embed(e: dict) -> str:
        """
        Flatten embed description and fields into plain text.
        """
        text = e.get("description", "") or ""
        if not text and e.get("fields"):
            text = "\n".join(f"{f['name']}: {f['value']}" for f in e["fields"])
        return text

    # Private notifications: Discord DM then fallback
    if private:
        for user in recipients:
            success = send_discord_dm(user=user, embed=embed, message=message)
            if not success:
                fallback_msg = message or extract_text_from_embed(embed or {})
                alliance_notify(
                    user=user,
                    title=title or (embed.get("title") if embed else "Notification"),
                    message=fallback_msg,
                    level=level,
                )
                logger.info(
                    f"[Fallback] AllianceAuth notification sent to {user.username}"
                )
        return

    # Public notification via webhook
    sent = False
    if embed or message:
        sent = send_webhook_notification(embed=embed, content=message)

    if sent:
        return

    # Fallback to AllianceAuth for public announcements
    fallback_msg = message or ""
    if embed and not message:
        fallback_msg = extract_text_from_embed(embed)
    for user in recipients:
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fallback_msg,
                level=level,
            )
            logger.info(f"AllianceAuth notification sent to {user.username}")
        except Exception as e:
            logger.error(
                f"AllianceAuth notify failed for {user.username}: {e}", exc_info=True
            )


def notify_alliance(user, title: str, message: str, level: str = "info"):
    """
    Send a single notification via AllianceAuth's internal system.
    """
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info(f"AllianceAuth '{title}' sent to {user.username}")
    except Exception as e:
        logger.error(
            f"AllianceAuth notify failed for {user.username}: {e}", exc_info=True
        )
