# fortunaisk/signals/ticket_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TicketPurchase, Winner
from .notifications import send_alliance_auth_notification
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TicketPurchase)
def notify_ticket_purchase(sender, instance, created, **kwargs):
    if created and instance.status == "processed":
        try:
            send_alliance_auth_notification(
                user=instance.user,
                title="Ticket Purchase Confirmation",
                message=(
                    f"Hello {instance.user.username},\n\n"
                    f"You have successfully purchased a ticket for the lottery '{instance.lottery.lottery_reference}' "
                    f"at the price of {instance.amount} ISK. Good luck!"
                ),
                level="info",
            )
            logger.info(f"Ticket purchase notification sent to {instance.user.username}.")
        except Exception as e:
            logger.error(f"Failed to send ticket purchase notification to {instance.user.username}: {e}", exc_info=True)


@receiver(post_save, sender=Winner)
def notify_winner(sender, instance, created, **kwargs):
    if created:
        try:
            send_alliance_auth_notification(
                user=instance.ticket.user,
                title="Congratulations, You've Won!",
                message=(
                    f"Hello {instance.ticket.user.username},\n\n"
                    f"Congratulations! You have won {instance.prize_amount} ISK in the lottery "
                    f"'{instance.ticket.lottery.lottery_reference}'. Your character {instance.character.character_name} "
                    f"is now a winner. Thank you for participating!"
                ),
                level="success",
            )
            logger.info(f"Winner notification sent to {instance.ticket.user.username}.")
        except Exception as e:
            logger.error(f"Failed to send winner notification to {instance.ticket.user.username}: {e}", exc_info=True)
