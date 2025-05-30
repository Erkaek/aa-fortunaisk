# fortunaisk/signals/notifications_signals.py

# Standard Library
import logging

# Django
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import TicketAnomaly, TicketPurchase, Winner
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)


def get_admin_users_queryset():
    User = get_user_model()
    return User.objects.filter(groups__permissions__codename="can_admin_app").distinct()


# ─── TicketPurchase: track diffs & DM purchaser only ─────────────────────────


@receiver(pre_save, sender=TicketPurchase)
def track_ticketpurchase_old_values(sender, instance, **kwargs):
    """Before saving, store old quantity and amount."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._old_quantity = old.quantity
            instance._old_amount = old.amount
        except sender.DoesNotExist:
            instance._old_quantity = 0
            instance._old_amount = 0
    else:
        instance._old_quantity = 0
        instance._old_amount = 0


@receiver(post_save, sender=TicketPurchase)
def notify_ticketpurchase_change(sender, instance, created, **kwargs):
    """
    After saving, if the user has added tickets,
    send them a DM confirming their purchase.
    """
    old_q = getattr(instance, "_old_quantity", 0)
    new_q = instance.quantity
    added_q = new_q - old_q

    old_a = getattr(instance, "_old_amount", 0)
    new_a = instance.amount
    added_a = new_a - old_a

    if added_q <= 0 or added_a <= 0:
        return

    embed = build_embed(
        title="🍀 Ticket Purchase Confirmed",
        description=(
            f"Hello {instance.user.username},\n\n"
            f"Your payment of {added_a:,} ISK for lottery "
            f"{instance.lottery.lottery_reference} has been processed.\n"
            f"You now have {new_q:,} ticket(s).\n\nGood luck! 🍀"
        ),
        level="success",
    )
    notify_discord_or_fallback(
        users=instance.user,
        event="ticket_purchase",
        embed=embed,
        private=True,
    )


# ─── TicketAnomaly: DM user + public alert ───────────────────────────────────


@receiver(post_save, sender=TicketAnomaly)
def on_anomaly_created(sender, instance, created, **kwargs):
    """When an anomaly is created, DM to the user + public alert to admins."""
    if not created or not instance.user:
        return

    lot_ref = getattr(instance.lottery, "lottery_reference", "N/A")

    # DM
    dm_embed = build_embed(
        title="⚠️ Payment Anomaly Detected",
        description=(
            f"Hello {instance.user.username},\n\n"
            f"An anomaly occurred for your payment of {instance.amount:,} ISK "
            f"on lottery {lot_ref}.\n\nReason: {instance.reason}"
        ),
        level="error",
    )
    notify_discord_or_fallback(
        users=instance.user,
        event="anomaly_detected",
        embed=dm_embed,
        private=True,
    )

    # Public (admins)
    public_embed = build_embed(
        title="⚠️ New Payment Anomaly",
        description=(
            f"User {instance.user.username} had an anomaly of {instance.amount:,} ISK "
            f"on lottery {lot_ref}: {instance.reason}"
        ),
        level="warning",
    )
    notify_discord_or_fallback(
        users=get_admin_users_queryset(),
        event="anomaly_detected",
        embed=public_embed,
        private=False,
    )


@receiver(post_save, sender=TicketAnomaly)
def on_anomaly_resolved(sender, instance, created, **kwargs):
    """When an anomaly is resolved, DM to the user + public confirmation."""
    if created or not instance.solved or not instance.user:
        return

    user = instance.user
    reason = instance.reason
    amount = f"{instance.amount:,} ISK"
    resolver = instance.solved_by.username if instance.solved_by else "Unknown"
    details = instance.detail or None

    # Build message for AllianceAuth DM
    dm_lines = [
        f"Hello {user.username},",
        "",
        "Your payment anomaly has been resolved. Here are the details:",
        f"• Reason: {reason}",
        f"• Amount: {amount}",
        f"• Resolved by: {resolver}",
    ]
    if details:
        dm_lines.append(f"• Resolution Details: {details}")
    dm_lines.append("")  # empty line
    dm_lines.append("Thank you for your patience! 🍀")
    dm_message = "\n".join(dm_lines)

    notify_discord_or_fallback(
        users=user,
        title="✅ Anomaly Resolved",
        message=dm_message,
        level="info",
        private=True,
    )

    # --- Public confirmation for admins (Discord embed) ---
    # Reusing get_admin_users_queryset defined above
    public_embed = build_embed(
        title="✅ Anomaly Resolved",
        description=f"Anomaly for {user.username} has been resolved.",
        level="info",
    )
    public_embed["fields"] = [
        {"name": "User", "value": user.username, "inline": True},
        {"name": "Reason", "value": reason, "inline": False},
        {"name": "Amount", "value": amount, "inline": True},
        {"name": "Resolved by", "value": resolver, "inline": True},
    ]
    if details:
        public_embed["fields"].append(
            {"name": "Details", "value": details, "inline": False}
        )

    notify_discord_or_fallback(
        users=get_admin_users_queryset(),
        event="anomaly_resolved",
        embed=public_embed,
        private=False,
    )


# ─── Winner: DM winner on creation, alert admin when prize distributed ──────


@receiver(post_save, sender=Winner)
def on_winner_created(sender, instance, created, **kwargs):
    """When a Winner is created, DM the winner."""
    if not created:
        return

    embed = build_embed(
        title="🎉 Congratulations, You Won!",
        description=(
            f"Hello {instance.ticket.user.username},\n\n"
            f"You have won {instance.prize_amount:,} ISK "
            f"in lottery {instance.ticket.lottery.lottery_reference}. Well done!"
        ),
        level="success",
    )
    notify_discord_or_fallback(
        users=instance.ticket.user,
        event="lottery_completed",
        embed=embed,
        private=True,
    )


@receiver(pre_save, sender=Winner)
def on_prize_distributed(sender, instance, **kwargs):
    """When distributed=True is set, DM the winner and send public notification."""
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    if not old.distributed and instance.distributed:
        # 1. Private notification to winner (keep existing)
        winner_embed = build_embed(
            title="🎁 Prize Distributed",
            description=(
                f"Hello {instance.ticket.user.username},\n\n"
                f"Your prize of {instance.prize_amount:,} ISK for lottery "
                f"{instance.ticket.lottery.lottery_reference} has just been distributed."
            ),
            level="info",
        )
        notify_discord_or_fallback(
            users=instance.ticket.user,
            event="prize_distributed",
            embed=winner_embed,
            private=True,
        )

        # 2. Public notification to Discord webhook
        admin_users = get_admin_users_queryset()

        # More detailed embed for public announcement
        public_embed = build_embed(
            title="💰 Lottery Prize Distributed",
            description=(
                f"A prize has been distributed for lottery **{instance.ticket.lottery.lottery_reference}**"
            ),
            fields=[
                {
                    "name": "Winner",
                    "value": instance.ticket.user.username,
                    "inline": True,
                },
                {
                    "name": "Amount",
                    "value": f"{instance.prize_amount:,} ISK",
                    "inline": True,
                },
                {
                    "name": "Distributed by",
                    "value": (
                        instance.distributed_by.username
                        if instance.distributed_by
                        else "System"
                    ),
                    "inline": True,
                },
            ],
            level="success",
        )

        notify_discord_or_fallback(
            users=admin_users,
            event="prize_distributed",
            embed=public_embed,
            private=False,  # Public notification
        )
