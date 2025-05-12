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
from allianceauth.notifications import notify as alliance_notify

# fortunaisk
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)

# Discord embed colors per level
LEVEL_COLORS = {
    "info": 0x3498DB,  # blue
    "success": 0x2ECC71,  # green
    "warning": 0xF1C40F,  # yellow
    "error": 0xE74C3C,  # red
}


def build_embed(
    title: str, description: str = None, fields: list[dict] = None, level: str = "info"
) -> dict:
    """
    Build a Discord embed payload with a timestamp, color, optional description and fields.
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
    Send an embed or plain content via Discord webhook.
    Returns True on HTTP 2xx, False otherwise.
    """
    url = get_webhook_url()
    if not url:
        logger.warning("Discord webhook not configured; skipping public announcement.")
        return False

    payload: dict = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("Discord webhook message sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to send Discord webhook message: {e}", exc_info=True)
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

    - If private=True → skip public webhook entirely, send only per-user via AllianceAuth.
    - Else:
      1) Send a single public webhook announcement (embed or message).
      2) If that fails (or if private=True), send per-user AllianceAuth notifications.

    Parameters:
    - users: User | QuerySet[User] | list[User]
    - title: title for the embed or AllianceAuth fallback
    - message: plain-text content
    - embed: full Discord embed dict (if provided, overrides title/message)
    - level: one of 'info','success','warning','error' (for embed color & AllianceAuth level)
    - private: bool, if True do not attempt webhook at all
    """
    # build minimal embed if none provided
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    # normalize recipients to list
    if isinstance(users, QuerySet):
        recipients = list(users)
    elif isinstance(users, (list, tuple)):
        recipients = list(users)
    else:
        recipients = [users]

    # 1) Public webhook
    sent_webhook = False
    if not private and (embed or message):
        sent_webhook = send_webhook_notification(embed=embed, content=message)

    # 2) Per-user fallback via AllianceAuth
    #    If webhook succeeded and not private, skip individual notifications.
    if sent_webhook and not private:
        return

    # assemble fallback message from embed if needed
    if message:
        fallback_message = message
    elif embed:
        # prefer description
        fallback_message = embed.get("description", "")
        # if no description, flatten fields
        if not fallback_message and embed.get("fields"):
            lines = []
            for f in embed["fields"]:
                name = f.get("name", "")
                val = f.get("value", "")
                lines.append(f"{name}: {val}")
            fallback_message = "\n".join(lines)
    else:
        fallback_message = ""

    for user in recipients:
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fallback_message,
                level=level,
            )
            logger.info(f"AllianceAuth notification sent to {user.username}")
        except Exception as e:
            logger.error(
                f"AllianceAuth notify failed for {user.username}: {e}", exc_info=True
            )


def notify_alliance(user, title: str, message: str, level: str = "info"):
    """
    Send a single notification via AllianceAuth's built-in system.
    """
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info(f"AllianceAuth '{title}' sent to {user.username}")
    except Exception as e:
        logger.error(
            f"AllianceAuth notify failed for {user.username}: {e}", exc_info=True
        )
