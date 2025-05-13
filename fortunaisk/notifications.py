# fortunaisk/notifications.py

import logging
from datetime import datetime

import requests
from django.core.cache import cache
from django.db.models import QuerySet

from allianceauth.notifications import notify as alliance_notify
from discordnotify.client import DiscordProxyClient  # ⚠️ via aa-discordnotify
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)

# client unique pour envoyer les DMs
proxy_client = DiscordProxyClient()

LEVEL_COLORS = {
    "info":    0x3498DB,
    "success": 0x2ECC71,
    "warning": 0xF1C40F,
    "error":   0xE74C3C,
}


def build_embed(title: str, description: str = None, fields: list[dict] = None, level: str = "info") -> dict:
    embed = {
        "title":     title,
        "color":     LEVEL_COLORS.get(level, LEVEL_COLORS["info"]),
        "timestamp": datetime.utcnow().isoformat(),
        "footer":    {"text": "Good luck to all participants! 🍀"},
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = fields
    logger.debug("[build_embed] %r", embed)
    return embed


def get_webhook_url() -> str:
    url = cache.get("discord_webhook_url")
    if url is None:
        cfg = WebhookConfiguration.objects.first()
        url = cfg.webhook_url if cfg and cfg.webhook_url else ""
        cache.set("discord_webhook_url", url or "", 300)
        logger.debug("[get_webhook_url] fetched from DB: %r", url)
    else:
        logger.debug("[get_webhook_url] fetched from cache: %r", url)
    return url


def send_webhook_notification(embed: dict = None, content: str = None) -> bool:
    url = get_webhook_url()
    if not url:
        logger.warning("[send_webhook] no webhook URL configured")
        return False

    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    logger.debug("[send_webhook] POST %s payload=%r", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("[send_webhook] success status=%s", resp.status_code)
        return True
    except Exception as exc:
        status = getattr(exc, "response", None) and exc.response.status_code
        body   = getattr(exc, "response", None) and exc.response.text
        logger.error("[send_webhook] failed status=%s exc=%s body=%r",
                     status, exc, body, exc_info=True)
        return False


def send_discord_dm(user, embed: dict = None, content: str = None) -> bool:
    """
    Envoie un MP Discord via le proxy DiscordNotify.
    """
    try:
        logger.debug(
            "[send_dm] proxy_client.send user=%s embed=%r content=%r",
            user.username, embed, content,
        )
        proxy_client.send(user=user, content=content or "", embed=embed)
        logger.info("[send_dm] sent DM to %s via DiscordProxy", user.username)
        return True
    except Exception as exc:
        logger.error("[send_dm] error for %s: %s", user.username, exc, exc_info=True)
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
    - Si private=True → MP Discord via proxy + fallback AllianceAuth.
    - Sinon → webhook public + fallback AllianceAuth.
    """
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    if isinstance(users, QuerySet):
        recipients = list(users)
    elif isinstance(users, (list, tuple)):
        recipients = users
    else:
        recipients = [users]

    logger.debug(
        "[notify] private=%s recipients=%s title=%r message=%r",
        private, [u.username for u in recipients], title, message,
    )

    def flatten(e: dict) -> str:
        txt = e.get("description", "") or ""
        if not txt and e.get("fields"):
            txt = "\n".join(f"{f['name']}: {f['value']}" for f in e["fields"])
        return txt

    # PRIVATE → DM Discord puis fallback
    if private:
        for user in recipients:
            ok = send_discord_dm(user=user, embed=embed, content=message)
            if not ok:
                fb = message or (embed and flatten(embed)) or ""
                logger.info("[notify][fallback] DM failed %s → AllianceAuth %r", user.username, fb)
                alliance_notify(
                    user=user,
                    title=title or (embed.get("title") if embed else "Notification"),
                    message=fb,
                    level=level,
                )
        return

    # PUBLIC → webhook
    if embed or message:
        if send_webhook_notification(embed=embed, content=message):
            return
        logger.warning("[notify] webhook failed, fallback per-user")

    fb = message or ""
    if embed and not message:
        fb = flatten(embed)

    for user in recipients:
        logger.debug("[notify][fallback] AllianceAuth to %s → %r", user.username, fb)
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fb,
                level=level,
            )
            logger.info("[notify][fallback] sent to %s", user.username)
        except Exception as exc:
            logger.error("[notify][fallback] error %s: %s", user.username, exc, exc_info=True)


def notify_alliance(user, title: str, message: str, level: str = "info"):
    logger.debug("[notify_alliance] user=%s title=%r message=%r", user.username, title, message)
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info("[notify_alliance] sent to %s", user.username)
    except Exception as exc:
        logger.error("[notify_alliance] error %s: %s", user.username, exc, exc_info=True)
