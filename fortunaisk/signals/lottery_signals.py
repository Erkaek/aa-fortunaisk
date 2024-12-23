# fortunaisk/signals/lottery_signals.py

# Standard Library
import logging

# Django
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import Lottery, Winner
from fortunaisk.notifications import send_discord_notification

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    """
    Avant de sauvegarder une loterie, récupérer l'ancien statut pour comparaison.
    """
    if instance.pk:
        try:
            old_instance = Lottery.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Lottery.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    """
    Après avoir sauvegardé une loterie, comparer l'ancien statut au nouveau et envoyer des notifications si nécessaire.
    """
    if created:
        # Notification de création
        embed = {
            "title": "Nouvelle Loterie Créée!",
            "color": 3066993,  # Vert
            "fields": [
                {
                    "name": "Référence",
                    "value": instance.lottery_reference,
                    "inline": False,
                },
                {
                    "name": "Prix du Ticket",
                    "value": f"{instance.ticket_price} ISK",
                    "inline": False,
                },
                {
                    "name": "Date de Fin",
                    "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": False,
                },
                {
                    "name": "Récepteur de Paiement",
                    "value": str(instance.payment_receiver),
                    "inline": False,
                },
            ],
        }
        send_discord_notification(embed=embed)
    else:
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            if instance.status == "completed":
                message = f"La loterie {instance.lottery_reference} a été complétée."
            elif instance.status == "cancelled":
                message = f"La loterie {instance.lottery_reference} a été annulée."
            else:
                message = f"La loterie {instance.lottery_reference} a été mise à jour."
            send_discord_notification(message=message)


@receiver(pre_delete, sender=Lottery)
def notify_discord_on_lottery_deletion(sender, instance: Lottery, **kwargs):
    """
    Avant de supprimer une loterie, envoyer une notification.
    """
    embed = {
        "title": "Loterie Supprimée!",
        "color": 15158332,  # Rouge
        "fields": [
            {"name": "Référence", "value": instance.lottery_reference, "inline": False},
            {"name": "Statut", "value": "Supprimée", "inline": False},
        ],
    }
    send_discord_notification(embed=embed)


@receiver(post_save, sender=Winner)
def notify_discord_on_winner_creation(
    sender, instance: Winner, created: bool, **kwargs
):
    """
    Après la création d'un gagnant, envoyer une notification.
    """
    if created:
        send_discord_notification(
            message=f"Félicitations {instance.ticket.user.username}, vous avez gagné la loterie '{instance.ticket.lottery.lottery_reference}'!"
        )
