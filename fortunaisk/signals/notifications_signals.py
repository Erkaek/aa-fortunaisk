# fortunaisk/signals/notifications_signals.py

# Standard Library
import logging

# Django
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import Lottery, TicketAnomaly, TicketPurchase, Winner
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)


def get_admin_users_queryset():
    User = get_user_model()
    return User.objects.filter(groups__permissions__codename="can_admin_app").distinct()


# ─── TicketPurchase: track diffs & notify ──────────────────────────────────────


@receiver(pre_save, sender=TicketPurchase)
def _track_ticketpurchase_old_values(sender, instance, **kwargs):
    """
    Avant save, on mémorise l'ancienne quantité et le montant
    pour calculer le delta en post_save.
    """
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
def _notify_ticketpurchase_change(sender, instance, created, **kwargs):
    """
    Après save, on envoie la notif Only si on a ajouté des tickets.
    Affiche le montant et la quantité **de cette transaction**.
    """
    old_q = getattr(instance, "_old_quantity", 0)
    new_q = instance.quantity
    added_q = new_q - old_q

    old_a = getattr(instance, "_old_amount", 0)
    new_a = instance.amount
    added_a = new_a - old_a

    # Debug log pour vérifier qu'on capte bien le delta
    logger.debug(
        f"[notify_ticketpurchase] lot={instance.lottery.lottery_reference} "
        f"user={instance.user.username} old_qty={old_q} new_qty={new_q} added_qty={added_q} "
        f"old_amt={old_a} new_amt={new_a} added_amt={added_a}"
    )

    # Si aucune valeur positive ajoutée, on ne notifie pas
    if added_q <= 0 or added_a <= 0:
        return

    embed = build_embed(
        title="🍀 Ticket Purchase Confirmed",
        description=(
            f"Hello {instance.user.username},\n\n"
            f"Your payment of **{added_a:,} ISK** for lottery "
            f"**{instance.lottery.lottery_reference}** has been processed. "
            f"You now have **{new_q:,}** ticket(s).\n\nGood luck! 🍀"
        ),
        level="success",
    )
    notify_discord_or_fallback(
        users=instance.user,
        embed=embed,
        private=True,
    )


# ─── TicketAnomaly: create & resolve ──────────────────────────────────────────


@receiver(post_save, sender=TicketAnomaly)
def on_anomaly_created(sender, instance, created, **kwargs):
    if created and instance.user:
        lot_ref = instance.lottery.lottery_reference if instance.lottery else "N/A"
        embed = build_embed(
            title="⚠️ Payment Anomaly Detected",
            description=(
                f"Hello {instance.user.username},\n\n"
                f"An anomaly occurred for your payment of **{instance.amount:,} ISK** "
                f"on lottery **{lot_ref}**.\n\nReason: *{instance.reason}*"
            ),
            level="error",
        )
        notify_discord_or_fallback(
            users=instance.user,
            embed=embed,
            private=True,
        )


@receiver(post_delete, sender=TicketAnomaly)
def on_anomaly_resolved(sender, instance, **kwargs):
    if instance.user:
        lot_ref = instance.lottery.lottery_reference if instance.lottery else "N/A"
        embed = build_embed(
            title="✅ Anomaly Resolved",
            description=(
                f"Hello {instance.user.username},\n\n"
                f"Your anomaly on lottery **{lot_ref}** has been resolved. Thank you!"
            ),
            level="info",
        )
        notify_discord_or_fallback(
            users=instance.user,
            embed=embed,
            private=True,
        )


# ─── Winner: notify on creation & distribution ───────────────────────────────


@receiver(post_save, sender=Winner)
def on_winner_created(sender, instance, created, **kwargs):
    if created:
        embed = build_embed(
            title="🎉 Congratulations, You Won!",
            description=(
                f"Hello {instance.ticket.user.username},\n\n"
                f"You have won **{instance.prize_amount:,} ISK** "
                f"in lottery **{instance.ticket.lottery.lottery_reference}**. Well done!"
            ),
            level="success",
        )
        notify_discord_or_fallback(
            users=instance.ticket.user,
            embed=embed,
            private=True,
        )


@receiver(pre_save, sender=Winner)
def on_prize_distributed(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if not old.distributed and instance.distributed:
        embed = build_embed(
            title="🎁 Prize Distributed",
            description=(
                f"Hello {instance.ticket.user.username},\n\n"
                f"Your prize of **{instance.prize_amount:,} ISK** "
                f"for lottery **{instance.ticket.lottery.lottery_reference}** has just been distributed."
            ),
            level="info",
        )
        notify_discord_or_fallback(
            users=instance.ticket.user,
            embed=embed,
            private=True,
        )


# ─── Lottery lifecycle: creation & status changes ────────────────────────────


@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_status = sender.objects.get(pk=instance.pk).status
        except sender.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    admins = get_admin_users_queryset()

    if created:
        fields = [
            {
                "name": "📌 Reference",
                "value": instance.lottery_reference,
                "inline": False,
            },
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
                    f"• Winner {i+1}: {p}%"
                    for i, p in enumerate(instance.winners_distribution or [])
                )
                or "None",
                "inline": False,
            },
        ]
        embed = build_embed(
            title="✨ New Lottery Created! ✨",
            description="Good luck to everyone! 🍀",
            fields=fields,
            level="info",
        )
        notify_discord_or_fallback(
            users=admins,
            embed=embed,
            private=False,
        )
        return

    old, new = instance._old_status, instance.status

    if old == "active" and new == "pending":
        embed = build_embed(
            title="🔒 Ticket Sales Closed",
            description=f"Sales for **{instance.lottery_reference}** are now closed. Winners coming soon!",
            level="warning",
        )
        notify_discord_or_fallback(users=admins, embed=embed, private=False)

    elif new == "completed":
        winners = list(instance.winners.select_related("ticket__user"))
        desc = (
            "\n".join(
                f"• {w.ticket.user.username}: **{w.prize_amount:,} ISK**"
                for w in winners
            )
            or "No winners."
        )
        embed = build_embed(
            title="🏆 Lottery Completed 🏆",
            description=desc,
            level="success",
        )
        notify_discord_or_fallback(users=admins, embed=embed, private=False)

    elif new == "cancelled":
        embed = build_embed(
            title="🚫 Lottery Cancelled 🚫",
            description=f"Lottery **{instance.lottery_reference}** has been cancelled by the admin.",
            level="error",
        )
        notify_discord_or_fallback(users=admins, embed=embed, private=False)
