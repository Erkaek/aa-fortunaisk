# fortunaisk/notifications.py

# Standard library
# Standard Library
import logging
from datetime import datetime

# Third Party
# Third-party
import requests

# Django
from django.core.cache import cache
from django.db.models import QuerySet

# Alliance Auth
# AllianceAuth notifications
from allianceauth.notifications import notify as alliance_notify

# AllianceAuth Discord service for DMs
try:
    # Alliance Auth
    from allianceauth.services.modules.discord import DiscordBotService

    discord_service = DiscordBotService()
except ImportError:
    discord_service = None

# fortunaisk
# Local models
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
        logger.warning("Public Discord webhook not configured; skipping announcement.")
        return False

    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("Public Discord webhook message sent.")
        return True
    except Exception as e:
        logger.error(
            "Failed to send public Discord webhook message: %s", e, exc_info=True
        )
        return False


def send_discord_dm(user, embed: dict = None, message: str = None) -> bool:
    """
    Attempt to send a private Discord DM via AllianceAuth's built-in Discord service.
    Returns True if sent or queued, False otherwise.
    """
    if discord_service is None or not discord_service.enabled:
        logger.warning("Discord service not available; cannot send DM.")
        return False

    try:
        # service.send_message will handle embeds or plain text
        discord_service.send_message(user=user, embed=embed, message=message or "")
        logger.info("Queued Discord DM for %s", user.username)
        return True
    except Exception as e:
        logger.error(
            "Failed to send Discord DM to %s: %s", user.username, e, exc_info=True
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
        1) Try sending a Discord DM via DiscordBotService.
        2) If that fails, fallback to AllianceAuth notifications.
    - Else:
        1) Send a public Discord webhook announcement.
        2) If that fails, fallback per-user to AllianceAuth notifications.
    """
    # If only title/message provided, build a minimal embed
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    # Normalize recipients to a list
    if isinstance(users, QuerySet):
        recipients = list(users)
    elif isinstance(users, (list, tuple)):
        recipients = users
    else:
        recipients = [users]

    def flatten_embed(e: dict) -> str:
        """
        Flatten embed description + fields into plain text for AllianceAuth fallback.
        """
        text = e.get("description", "") or ""
        if not text and e.get("fields"):
            text = "\n".join(f"{f['name']}: {f['value']}" for f in e["fields"])
        return text

    # PRIVATE: Discord DM first, then AllianceAuth fallback
    if private:
        for user in recipients:
            ok = send_discord_dm(user=user, embed=embed, message=message)
            if not ok:
                fallback_msg = message or (embed and flatten_embed(embed)) or ""
                alliance_notify(
                    user=user,
                    title=title or (embed.get("title") if embed else "Notification"),
                    message=fallback_msg,
                    level=level,
                )
                logger.info(
                    "AllianceAuth fallback notification sent to %s", user.username
                )
        return

    # PUBLIC: webhook first…
    if embed or message:
        sent = send_webhook_notification(embed=embed, content=message)
        if sent:
            return

    # …then per-user AllianceAuth fallback
    fb = message or ""
    if embed and not message:
        fb = flatten_embed(embed)
    for user in recipients:
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fb,
                level=level,
            )
            logger.info("AllianceAuth notification sent to %s", user.username)
        except Exception as e:
            logger.error(
                "AllianceAuth notify failed for %s: %s", user.username, e, exc_info=True
            )


def notify_alliance(user, title: str, message: str, level: str = "info"):
    """
    Send a single notification via AllianceAuth's internal system.
    """
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info("AllianceAuth '%s' sent to %s", title, user.username)
    except Exception as e:
        logger.error(
            "AllianceAuth notify failed for %s: %s", user.username, e, exc_info=True
        )
