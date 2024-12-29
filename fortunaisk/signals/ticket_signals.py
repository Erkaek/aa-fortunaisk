# fortunaisk/signals/ticket_signals.py

# Standard Library
import logging

# Django
from django.db.models.signals import post_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import TicketAnomaly, TicketPurchase, Winner
from fortunaisk.notifications import send_alliance_auth_notification

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TicketPurchase)
def notify_ticket_purchase(sender, instance, created, **kwargs):
    if created and instance.status == "processed":
        try:
            send_alliance_auth_notification(
                user=instance.user,
                title="Confirmation d'Achat de Ticket",
                message=(
                    f"Bonjour {instance.user.username},\n\n"
                    f"Vous avez réussi à acheter un ticket pour la loterie '{instance.lottery.lottery_reference}' "
                    f"au prix de {instance.amount} ISK. Bonne chance !"
                ),
                level="info",
            )
            logger.info(
                f"Ticket purchase notification sent to {instance.user.username}."
            )
        except Exception as e:
            logger.error(
                f"Failed to send ticket purchase notification to {instance.user.username}: {e}",
                exc_info=True,
            )


@receiver(post_save, sender=Winner)
def notify_winner(sender, instance, created, **kwargs):
    if created:
        try:
            send_alliance_auth_notification(
                user=instance.ticket.user,
                title="Félicitations, Vous avez Gagné !",
                message=(
                    f"Bonjour {instance.ticket.user.username},\n\n"
                    f"Félicitations ! Vous avez gagné {instance.prize_amount} ISK dans la loterie "
                    f"'{instance.ticket.lottery.lottery_reference}'. Votre personnage {instance.character.character_name} "
                    f"est maintenant un gagnant. Merci de votre participation !"
                ),
                level="success",
            )
            logger.info(f"Winner notification sent to {instance.ticket.user.username}.")
        except Exception as e:
            logger.error(
                f"Failed to send winner notification to {instance.ticket.user.username}: {e}",
                exc_info=True,
            )


@receiver(post_save, sender=TicketAnomaly)
def notify_ticket_anomaly(sender, instance, created, **kwargs):
    if created and instance.user:
        try:
            send_alliance_auth_notification(
                user=instance.user,
                title="Anomalie lors de l'Achat de Ticket",
                message=(
                    f"Bonjour {instance.user.username},\n\n"
                    f"Une anomalie a été détectée lors de votre achat de ticket pour la loterie '{instance.lottery.lottery_reference}'.\n"
                    f"Raison : {instance.reason}\n"
                    f"Montant : {instance.amount} ISK\n\n"
                    f"Veuillez vérifier vos informations ou contacter le support si nécessaire."
                ),
                level="error",
            )
            logger.info(
                f"Anomaly notification sent to {instance.user.username} for payment ID {instance.payment_id}."
            )
        except Exception as e:
            logger.error(
                f"Failed to send anomaly notification to {instance.user.username}: {e}",
                exc_info=True,
            )
