# fortunaisk/signals/lottery_signals.py

# Standard Library
import logging

# Django
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

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
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=instance.payment_receiver
            )
            corp_name = corporation.corporation_name
        except EveCorporationInfo.DoesNotExist:
            corp_name = "Corporation Inconnue"

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
                    "value": corp_name,
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
                    try:
                        corporation = EveCorporationInfo.objects.get(
                            corporation_id=instance.payment_receiver
                        )
                        corp_name = corporation.corporation_name
                    except EveCorporationInfo.DoesNotExist:
                        corp_name = "Corporation Inconnue"

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
                            {
                                "name": "🔑 **Récepteur de Paiement**",
                                "value": corp_name,
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
                    try:
                        corporation = EveCorporationInfo.objects.get(
                            corporation_id=instance.payment_receiver
                        )
                        corp_name = corporation.corporation_name
                    except EveCorporationInfo.DoesNotExist:
                        corp_name = "Corporation Inconnue"

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
                            {
                                "name": "🔑 **Récepteur de Paiement**",
                                "value": corp_name,
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
                try:
                    corporation = EveCorporationInfo.objects.get(
                        corporation_id=instance.payment_receiver
                    )
                    corp_name = corporation.corporation_name
                except EveCorporationInfo.DoesNotExist:
                    corp_name = "Corporation Inconnue"

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
                        {
                            "name": "🔑 **Récepteur de Paiement**",
                            "value": corp_name,
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
