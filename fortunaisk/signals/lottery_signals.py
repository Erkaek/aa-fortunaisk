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
            "title": "✨ **Nouvelle Loterie Créée!** ✨",
            "color": 3066993,  # Vert
            "fields": [
                {
                    "name": "📌 **Référence**",
                    "value": instance.lottery_reference,
                    "inline": False,
                },
                {
                    "name": "💰 **Prix du Ticket**",
                    "value": f"{instance.ticket_price} ISK",
                    "inline": False,
                },
                {
                    "name": "📅 **Date de Fin**",
                    "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": False,
                },
                {
                    "name": "🔑 **Récepteur de Paiement**",
                    "value": str(instance.payment_receiver),
                    "inline": False,
                },
            ],
            "footer": {
                "text": "Bonne chance à tous! 🍀",
                "icon_url": "https://i.imgur.com/4M34hi2.png",  # Icône du footer
            },
            "timestamp": instance.start_date.isoformat(),
        }
        logger.debug(f"Envoi de l'embed de création: {embed}")
        send_discord_notification(embed=embed)
    else:
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            if instance.status == "completed":
                # Vérifier s'il y a des gagnants
                winners = Winner.objects.filter(ticket__lottery=instance)
                if winners.exists():
                    # Regrouper tous les gagnants dans un seul embed
                    winners_list = "\n".join(
                        [
                            f"**{winner.ticket.user.username}** ({winner.character.character_name}) - **{winner.prize_amount:,.2f} ISK**"
                            for winner in winners
                        ]
                    )
                    embed = {
                        "title": "🏆 **Gagnants de la Loterie!** 🏆",
                        "description": f"Félicitations aux gagnants de la loterie **{instance.lottery_reference}**! 🎉",
                        "color": 0x00FF00,  # Vert
                        "fields": [
                            {
                                "name": "📌 **Référence**",
                                "value": instance.lottery_reference,
                                "inline": False,
                            },
                            {
                                "name": "💰 **Prix Total**",
                                "value": f"{instance.total_pot} ISK",
                                "inline": False,
                            },
                            {
                                "name": "🎖️ **Gagnants**",
                                "value": winners_list,
                                "inline": False,
                            },
                            {
                                "name": "📅 **Date de Fin**",
                                "value": instance.end_date.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "inline": False,
                            },
                        ],
                        "footer": {
                            "text": "Bonne chance à tous! 🍀",
                            "icon_url": "https://i.imgur.com/4M34hi2.png",  # Icône du footer
                        },
                        "timestamp": instance.end_date.isoformat(),
                    }
                    logger.debug(f"Envoi de l'embed groupé des gagnants: {embed}")
                    send_discord_notification(embed=embed)
                else:
                    # Envoyer un embed indiquant qu'il n'y a pas eu de gagnant
                    embed = {
                        "title": "🎉 **Loterie Terminée sans Gagnant** 🎉",
                        "description": f"La loterie **{instance.lottery_reference}** a été terminée, mais aucun gagnant n'a été tiré. 😞",
                        "color": 0xFF0000,  # Rouge
                        "fields": [
                            {
                                "name": "📌 **Référence**",
                                "value": instance.lottery_reference,
                                "inline": False,
                            },
                            {
                                "name": "💰 **Prix Total**",
                                "value": f"{instance.total_pot} ISK",
                                "inline": False,
                            },
                            {
                                "name": "📅 **Date de Fin**",
                                "value": instance.end_date.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "inline": False,
                            },
                        ],
                        "footer": {
                            "text": "Bonne chance pour la prochaine fois! 🍀",
                            "icon_url": "https://i.imgur.com/4M34hi2.png",  # Icône du footer
                        },
                        "timestamp": instance.end_date.isoformat(),
                    }
                    logger.debug(
                        f"Envoi de l'embed de terminaison sans gagnant: {embed}"
                    )
                    send_discord_notification(embed=embed)
            elif instance.status == "cancelled":
                # Envoyer un embed indiquant que la loterie a été annulée
                embed = {
                    "title": "🚫 **Loterie Annulée** 🚫",
                    "description": f"La loterie **{instance.lottery_reference}** a été annulée. 🛑",
                    "color": 0xFF0000,  # Rouge
                    "fields": [
                        {
                            "name": "📌 **Référence**",
                            "value": instance.lottery_reference,
                            "inline": False,
                        },
                        {
                            "name": "🔄 **Statut**",
                            "value": "Annulée",
                            "inline": False,
                        },
                    ],
                    "footer": {
                        "text": "Loterie annulée par l'administrateur.",
                        "icon_url": "https://i.imgur.com/4M34hi2.png",  # Icône du footer
                    },
                    "timestamp": instance.end_date.isoformat(),
                }
                logger.debug(f"Envoi de l'embed d'annulation: {embed}")
                send_discord_notification(embed=embed)
            else:
                # Envoyer un message simple pour d'autres mises à jour
                message = (
                    f"La loterie **{instance.lottery_reference}** a été mise à jour. 📝"
                )
                logger.debug(f"Envoi du message de mise à jour: {message}")
                send_discord_notification(message=message)


@receiver(pre_delete, sender=Lottery)
def notify_discord_on_lottery_deletion(sender, instance: Lottery, **kwargs):
    """
    Avant de supprimer une loterie, envoyer une notification.
    """
    embed = {
        "title": "🗑️ **Loterie Supprimée!** 🗑️",
        "color": 15158332,  # Rouge
        "fields": [
            {
                "name": "📌 **Référence**",
                "value": instance.lottery_reference,
                "inline": False,
            },
            {"name": "🔄 **Statut**", "value": "Supprimée", "inline": False},
        ],
        "footer": {
            "text": "Loterie supprimée définitivement.",
            "icon_url": "https://i.imgur.com/4M34hi2.png",  # Icône du footer
        },
        "timestamp": instance.end_date.isoformat(),
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
        embed = {
            "title": "🏆 **Nouveau Gagnant!** 🏆",
            "description": f"Félicitations à **{instance.ticket.user.username}** qui a remporté la loterie **{instance.ticket.lottery.lottery_reference}**! 🎉",
            "color": 0x00FF00,  # Vert
            "thumbnail": {
                "url": "https://i.imgur.com/4M34hi2.png",  # Icône du gagnant
            },
            "fields": [
                {
                    "name": "📌 **Utilisateur**",
                    "value": instance.ticket.user.username,
                    "inline": True,
                },
                {
                    "name": "🛡️ **Personnage**",
                    "value": instance.character.character_name,
                    "inline": True,
                },
                {
                    "name": "💰 **Prix**",
                    "value": f"{instance.prize_amount:,.2f} ISK",
                    "inline": True,
                },
                {
                    "name": "📅 **Date de Gain**",
                    "value": instance.won_at.strftime("%Y-%m-%d %H:%M"),
                    "inline": False,
                },
            ],
            "footer": {
                "text": "Bonne chance à tous! 🍀",
                "icon_url": "https://i.imgur.com/4M34hi2.png",  # Icône du footer
            },
            "timestamp": instance.won_at.isoformat(),
        }
        send_discord_notification(embed=embed)
