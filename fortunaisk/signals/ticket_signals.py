# fortunaisk/signals/ticket_signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from fortunaisk.models import TicketAnomaly, Winner
from fortunaisk.notifications import send_ticket_anomaly_dm, send_winner_dm

logger = logging.getLogger(__name__)

@receiver(post_save, sender=TicketAnomaly)
def on_ticket_anomaly(sender, instance, created, **kwargs):
    if not created or not instance.user:
        return
    discord_id = instance.user.discord_id
    lottery_ref = instance.lottery.lottery_reference if instance.lottery else "Unknown"
    send_ticket_anomaly_dm(discord_id, lottery_ref, instance.reason, instance.amount)
    logger.info(f"Sent ticket anomaly DM to {instance.user.username} for lottery {lottery_ref}.")

@receiver(post_save, sender=Winner)
def on_winner(sender, instance, created, **kwargs):
    if not created:
        return
    discord_id = instance.ticket.user.discord_id
    lottery_ref = instance.ticket.lottery.lottery_reference
    send_winner_dm(discord_id, lottery_ref, instance.prize_amount, instance.ticket.id)
    logger.info(f"Sent winner DM to {instance.ticket.user.username} for lottery {lottery_ref}.")
