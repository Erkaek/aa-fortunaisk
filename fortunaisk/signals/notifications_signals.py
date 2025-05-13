# fortunaisk/signals/notifications_signals.py
import logging
from django.db.models.signals import pre_save, post_delete, post_save
from django.dispatch import receiver
from fortunaisk.models import Lottery, ProcessedPayment, TicketAnomaly, Winner
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)

def get_admin_users_queryset():
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.filter(groups__permissions__codename="can_admin_app").distinct()

@receiver(post_save, sender=ProcessedPayment)
def on_payment_processed(sender, instance, created, **kwargs):
    if not created:
        return
    from fortunaisk.models import TicketPurchase
    for pur in TicketPurchase.objects.filter(payment_id=instance.payment_id, status="processed"):
        embed = build_embed(
            title="🍀 Ticket Purchase Confirmed",
            description=(
                f"Hello {pur.user.username},\n\n"
                f"Your payment of **{pur.amount:,} ISK** for lottery **{pur.lottery.lottery_reference}** "
                f"has been processed. You now have **{pur.quantity}** ticket(s).\n\nGood luck! 🍀"
            ),
            level="success",
        )
        notify_discord_or_fallback(users=pur.user, embed=embed, private=True)

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
        notify_discord_or_fallback(users=instance.user, embed=embed, private=True)

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
        notify_discord_or_fallback(users=instance.user, embed=embed, private=True)

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
        notify_discord_or_fallback(users=instance.ticket.user, embed=embed, private=True)

@receiver(pre_save, sender=Winner)
def on_prize_distributed(sender, instance, **kwargs):
    if not instance.pk:
        return
    old = Winner.objects.get(pk=instance.pk)
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
        notify_discord_or_fallback(users=instance.ticket.user, embed=embed, private=True)

@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._old_status = Lottery.objects.get(pk=instance.pk).status
        except Lottery.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    admins = get_admin_users_queryset()
    if created:
        fields = [
            {"name": "📌 Reference", "value": instance.lottery_reference, "inline": False},
            {"name": "📅 End Date", "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"), "inline": False},
            {"name": "💰 Ticket Price", "value": f"{instance.ticket_price:,} ISK", "inline": False},
            {"name": "🎟️ Max Tickets / User", "value": str(instance.max_tickets_per_user or "Unlimited"), "inline": False},
            {"name": "🔑 Payment Receiver", "value": str(instance.payment_receiver), "inline": False},
            {"name": "🏆 # of Winners", "value": str(instance.winner_count), "inline": False},
            {"name": "📊 Prize Distribution", "value": "\n".join(
                f"• Winner {i+1}: {p}%" for i, p in enumerate(instance.winners_distribution or [])
            ) or "None", "inline": False},
        ]
        embed = build_embed(
            title="✨ New Lottery Created! ✨",
            description="Good luck to everyone! 🍀",
            fields=fields,
            level="info",
        )
        notify_discord_or_fallback(users=admins, embed=embed, private=False)
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
        desc = "\n".join(f"• {w.ticket.user.username}: **{w.prize_amount:,} ISK**" for w in winners) or "No winners."
        embed = build_embed(title="🏆 Lottery Completed 🏆", description=desc, level="success")
        notify_discord_or_fallback(users=admins, embed=embed, private=False)
    elif new == "cancelled":
        embed = build_embed(
            title="🚫 Lottery Cancelled 🚫",
            description=f"Lottery **{instance.lottery_reference}** has been cancelled by the admin.",
            level="error",
        )
        notify_discord_or_fallback(users=admins, embed=embed, private=False)
