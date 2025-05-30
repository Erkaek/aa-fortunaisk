# Standard Library
import logging
import random

# Django
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver

# fortunaisk
from fortunaisk.models import Lottery
from fortunaisk.models.winner_distribution import WinnerDistribution
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)

# Signal explicitly emitted after Lottery and its distributions are created
lottery_created = Signal()


def get_admin_users_queryset():
    """
    Returns users from the 'can_admin_app' group
    to send public notifications.
    """
    User = get_user_model()
    return User.objects.filter(groups__permissions__codename="can_admin_app").distinct()


@receiver(lottery_created)
def on_lottery_created(sender, instance, **kwargs):
    """
    Sends Discord embed after the Lottery and
    all its WinnerDistributions are created in database.
    """
    # 1) Reload percentages
    dist_qs = WinnerDistribution.objects.filter(
        lottery_reference__iexact=instance.lottery_reference
    ).order_by("winner_rank")

    # Formatting: remove .00 if percentage is integer
    distributions = []
    for wd in dist_qs:
        pct = wd.winner_prize_distribution
        if pct == pct.quantize(pct.normalize().scaleb(0)):
            pct_str = f"{int(pct)}%"
        else:
            pct_str = f"{pct.normalize()}%"
        distributions.append(pct_str)

    # 2) Build fields with emojis
    fields = [
        {"name": "📌 Reference", "value": instance.lottery_reference, "inline": False},
        {
            "name": "📅 End Date",
            "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"),
            "inline": False,
        },
        {
            "name": "💰 Ticket Price",
            "value": f"{instance.ticket_price:,} ISK",
            "inline": False,
        },
        {
            "name": "🎟️ Max Tickets / User",
            "value": str(instance.max_tickets_per_user or "Unlimited"),
            "inline": False,
        },
        {
            "name": "🔑 Payment Receiver",
            "value": str(instance.payment_receiver),
            "inline": False,
        },
        {
            "name": "🏆 # of Winners",
            "value": str(instance.winner_count),
            "inline": False,
        },
        {
            "name": "📊 Prize Distribution",
            "value": "\n".join(
                f"• Winner {i + 1}: {p}" for i, p in enumerate(distributions)
            ),
            "inline": False,
        },
    ]

    # 3) Create embed
    embed = build_embed(
        title="✨ New Lottery Created! ✨",
        description="Good luck to everyone! 🍀",
        fields=fields,
        level="success",
    )

    # 4) Send via configured webhooks
    notify_discord_or_fallback(
        users=get_admin_users_queryset(),
        event="lottery_created",
        embed=embed,
        private=False,
    )


@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    """Save old status to detect transitions later."""
    if instance.pk:
        try:
            instance._old_status = sender.objects.get(pk=instance.pk).status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Lottery)
def lottery_status_change(sender, instance, created, **kwargs):
    if created:
        return

    admins = get_admin_users_queryset()
    old = getattr(instance, "_old_status", None)
    new = instance.status

    # ─── Sales Closed ──────────────────────────────────────────────────────────
    if old == "active" and new == "pending":
        fun_messages = [
            "All tickets are in. Let's find out who gets lucky! 🤞",
            "The ticket window is shut. May the odds be ever in your favor! 🍀",
            "Sales closed – time to shake that magic hat! 🎩✨",
            "No more tickets! The suspense begins… 🔮",
            "That's all, folks! Winners draw coming soon! 🏆",
            "Doors are locked. Time to roll the dice! 🎲",
            "Bell rung on ticket sales! Let's see some winners! 🔔",
            "Ticket booth closed. Let the magic happen! ✨",
            "Hold onto your hats—drawing starts shortly! 🎩",
            "No extra tickets accepted. Good luck out there! 🍀",
            "Our ticket elves are busy sorting entries! 🧝‍♂️",
            "Tickets sealed. Fate will decide soon! ⚖️",
            "All aboard the winner train—departure imminent! 🚂",
            "That's a wrap on ticket sales—stay tuned! 📺",
            "Game face on! We're about to pick winners! 🎮",
            "Ticket box is closed. Let the draw commence! 📦",
            "Hold tight—drawing names from the hat now! 🎩",
            "No more entries. The lottery gods are listening! 🙏",
            "Last call's rung. Winner reveal on the horizon! 🌅",
        ]

        chosen = random.choice(fun_messages)

        embed = build_embed(
            title="🔒 Ticket Sales Closed",
            description=(
                f"Lottery **{instance.lottery_reference}** is now closed for purchases.\n\n"
                f"{chosen}"
            ),
            level="warning",
        )

        notify_discord_or_fallback(
            users=admins,
            event="lottery_sales_closed",
            embed=embed,
            private=False,
        )

    # ─── Lottery Completed ─────────────────────────────────────────────────────
    if new == "completed":
        # fortunaisk
        from fortunaisk.models import Winner

        winners = list(
            Winner.objects.filter(ticket__lottery=instance).order_by("won_at")
        )

        # Main message
        lines = [
            f"🎉 **Lottery {instance.lottery_reference} is finished!** 🎉",
            "",
            "Here's the podium 🏆:",
        ]
        emojis = ["🥇", "🥈", "🥉"]
        for idx, w in enumerate(winners, start=1):
            medal = emojis[idx - 1] if idx <= 3 else f"{idx}."
            lines.append(
                f"{medal} **{w.ticket.user.username}** → **{w.prize_amount:,} ISK**"
            )

        if not winners:
            lines.append("😢 No tickets sold, no winners this time.")

        description = "\n".join(lines)

        embed = build_embed(
            title="🏆 Lottery Completed! 🏆",
            description=description,
            level="success",
            fields=[
                {
                    "name": "📌 Reference",
                    "value": instance.lottery_reference,
                    "inline": True,
                },
                {
                    "name": "🗓 Closed on",
                    "value": instance.end_date.strftime("%Y-%m-%d %H:%M"),
                    "inline": True,
                },
                {"name": "🥇 Winners", "value": str(len(winners)), "inline": True},
                {
                    "name": "💰 Total Pool",
                    "value": f"{instance.total_pot:,} ISK",
                    "inline": True,
                },
            ],
            footer={"text": "Thanks for playing! See you on the next adventure ✨"},
        )

        notify_discord_or_fallback(
            users=admins,
            event="lottery_completed",
            embed=embed,
            private=False,
        )

    # ─── Lottery Cancelled ─────────────────────────────────────────────────────
    if new == "cancelled":
        embed = build_embed(
            title="🚫 Lottery Cancelled 🚫",
            description=f"{instance.lottery_reference} was cancelled by an admin.",
            level="error",
        )
        notify_discord_or_fallback(
            users=admins,
            event="lottery_cancelled",
            embed=embed,
            private=False,
        )
