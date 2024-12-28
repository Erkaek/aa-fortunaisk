# fortunaisk/tasks.py

# Standard Library
import json
import logging

# Third Party
from celery import shared_task
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.apps import apps
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_purchased_tickets():
    """
    Vérifie les tickets achetés toutes les 5 minutes.
    """
    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
    try:
        # Exemple de logique : traiter les tickets en attente
        pending_tickets = TicketPurchase.objects.filter(status="pending")
        for ticket in pending_tickets:
            # Implémentez votre logique ici, par exemple, valider ou notifier
            logger.debug(
                f"Processing ticket {ticket.id} for user {ticket.user.username}"
            )
            # Exemple de traitement : marquer le ticket comme traité
            # ticket.status = 'processed'
            # ticket.save()
        logger.info("check_purchased_tickets exécutée avec succès.")
    except Exception as e:
        logger.error(f"Erreur dans check_purchased_tickets: {e}")


@shared_task
def check_lottery_status():
    """
    Vérifie l'état des loteries toutes les 15 minutes et clôture les loteries terminées.
    Avant de clôturer, revérifie les tickets achetés.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        now = timezone.now()
        active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
        for lottery in active_lotteries:
            # Revérifier les tickets achetés
            tickets = lottery.ticket_purchases.all()
            logger.debug(
                f"Revérification des tickets pour la loterie {lottery.lottery_reference}"
            )

            for ticket in tickets:
                # Implémentez votre logique de revérification ici
                logger.debug(
                    f"Checking ticket {ticket.id} for user {ticket.user.username}"
                )
                # Exemple de logique : vérifier si le ticket est toujours valide
                # if not ticket.is_valid():
                #     logger.warning(f"Ticket {ticket.id} pour l'utilisateur {ticket.user.username} n'est plus valide.")

            # Clôturer la loterie
            lottery.complete_lottery()
        logger.info("check_lottery_status exécutée avec succès.")
    except Exception as e:
        logger.error(f"Erreur dans check_lottery_status: {e}")


@shared_task
def create_lottery_from_auto_lottery(auto_lottery_id: int):
    """
    Crée une Lottery basée sur une AutoLottery spécifique.
    """
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        new_lottery = auto_lottery.create_lottery()
        logger.info(
            f"Created Lottery '{new_lottery.lottery_reference}' from AutoLottery '{auto_lottery.name}'"
        )
        return new_lottery.id
    except AutoLottery.DoesNotExist:
        logger.error(
            f"AutoLottery avec l'ID {auto_lottery_id} n'existe pas ou est inactive."
        )
    except Exception as e:
        logger.error(
            f"Erreur lors de la création de la Lottery depuis l'AutoLottery {auto_lottery_id}: {e}"
        )
    return None


def setup_periodic_tasks():
    """
    Configure les tâches périodiques globales pour FortunaIsk.
    """
    # Vérifier si la tâche 'check_purchased_tickets' existe déjà
    if not PeriodicTask.objects.filter(name="check_purchased_tickets").exists():
        # check_purchased_tickets => toutes les 5 minutes
        schedule_check_tickets, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.create(
            name="check_purchased_tickets",
            task="fortunaisk.tasks.check_purchased_tickets",
            interval=schedule_check_tickets,
            args=json.dumps([]),
        )
        logger.info("Periodic task 'check_purchased_tickets' créée.")

    # Vérifier si la tâche 'check_lottery_status' existe déjà
    if not PeriodicTask.objects.filter(name="check_lottery_status").exists():
        # check_lottery_status => toutes les 15 minutes
        schedule_check_lottery, created = IntervalSchedule.objects.get_or_create(
            every=15,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.create(
            name="check_lottery_status",
            task="fortunaisk.tasks.check_lottery_status",
            interval=schedule_check_lottery,
            args=json.dumps([]),
        )
        logger.info("Periodic task 'check_lottery_status' créée.")

    logger.info("Periodic tasks globales configurées avec succès.")
