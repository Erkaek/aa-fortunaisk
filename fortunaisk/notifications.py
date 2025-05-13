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

# Couleurs Discord embed par niveau
LEVEL_COLORS = {
    "info": 0x3498DB,  # bleu
    "success": 0x2ECC71,  # vert
    "warning": 0xF1C40F,  # jaune
    "error": 0xE74C3C,  # rouge
}


def build_embed(
    title: str, description: str = None, fields: list[dict] = None, level: str = "info"
) -> dict:
    """
    Construit un payload Discord embed (public webhook ou DM).
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
    logger.debug("[build_embed] %r", embed)
    return embed


def get_webhook_url() -> str | None:
    """
    Récupère l’URL du webhook public Discord (cache 5 min).
    """
    url = cache.get("discord_webhook_url")
    if url is None:
        cfg = WebhookConfiguration.objects.first()
        url = cfg.webhook_url if cfg and cfg.webhook_url else ""
        cache.set("discord_webhook_url", url or "", 300)
        logger.debug("[get_webhook_url] loaded from DB: %r", url)
    else:
        logger.debug("[get_webhook_url] loaded from cache: %r", url)
    return url or None


def send_webhook_notification(embed: dict = None, content: str = None) -> bool:
    """
    Envoie un embed ou un texte sur le webhook public Discord.
    """
    url = get_webhook_url()
    if not url:
        logger.warning("[send_webhook] no webhook URL configured")
        return False

    payload: dict = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    logger.debug("[send_webhook] POST %s %r", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("[send_webhook] success (status=%s)", resp.status_code)
        return True
    except Exception as exc:
        status = getattr(exc, "response", None) and exc.response.status_code
        body = getattr(exc, "response", None) and exc.response.text
        logger.error(
            "[send_webhook] failed status=%s body=%r exc=%s",
            status,
            body,
            exc,
            exc_info=True,
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
    - Si private=True → on crée une notification Alliance Auth par user
      (aa-discordnotify s’en chargera de la DMer sur Discord).
    - Sinon → on tente le webhook public ; si échec, on retombe sur per-user Alliance Auth.
    """
    # 1) Build minimal embed si besoin
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    # 2) Normalize recipients
    if isinstance(users, QuerySet):
        recipients = list(users)
    elif isinstance(users, (list, tuple)):
        recipients = users
    else:
        recipients = [users]

    # helper pour extraire du texte si besoin
    def _flatten(e: dict) -> str:
        txt = e.get("description", "") or ""
        if not txt and e.get("fields"):
            txt = "\n".join(f"{f['name']}: {f['value']}" for f in e["fields"])
        return txt

    # 3) Private path → AllianceAuth notify (aa-discordnotify forwardera en DM)
    if private:
        for u in recipients:
            fb = message or (_flatten(embed) if embed else "")
            alliance_notify(
                user=u,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fb,
                level=level,
            )
            logger.info(
                "[notify][private] queued AA notification for %s: %r",
                u.username,
                title or fb,
            )
        return

    # 4) Public path → webhook
    if embed or message:
        if send_webhook_notification(embed=embed, content=message):
            return
        logger.warning("[notify] public webhook failed, falling back to per-user")

    # 5) Fallback AllianceAuth per user
    fb = message or (_flatten(embed) if embed else "")
    for u in recipients:
        try:
            alliance_notify(
                user=u,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fb,
                level=level,
            )
            logger.info("[notify][fallback] sent AA notif to %s: %r", u.username, fb)
        except Exception as exc:
            logger.error(
                "[notify][fallback] error for %s: %s", u.username, exc, exc_info=True
            )


def notify_alliance(user, title: str, message: str, level: str = "info"):
    """
    Envoie simplement une notification via le système interne Alliance Auth.
    """
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info("[notify_alliance] sent to %s", user.username)
    except Exception as exc:
        logger.error(
            "[notify_alliance] failed for %s: %s", user.username, exc, exc_info=True
        )
