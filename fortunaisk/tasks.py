# Standard Library
import json
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.db import IntegrityError, transaction
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.tasks import QueueOnce

# Local imports
from .models import Lottery, TicketPurchase

logger = logging.getLogger(__name__)


# Tâche pour traiter les paiements de tickets pour toutes les loteries actives
@shared_task(bind=True, base=QueueOnce)
def process_wallet_tickets(self):
    """
    Process ticket purchases for all active lotteries by checking wallet entries.
    """
    # Étape 1 : Récupérer toutes les loteries actives
    active_lotteries = Lottery.objects.filter(status="active")

    if not active_lotteries.exists():
        logger.info("No active lotteries found.")
        return "No active lotteries to process."

    logger.info(
        f"Processing wallet entries for {len(active_lotteries)} active lotteries."
    )

    processed_entries = 0

    # Étape 2 : Traiter les paiements pour chaque loterie active
    for lottery in active_lotteries:
        payments = CorporationWalletJournalEntry.objects.filter(
            second_party_name_id=lottery.payment_receiver,
            amount=lottery.ticket_price,  # Utiliser le prix exact du ticket
            reason__contains=f"LOTTERY-{lottery.lottery_reference}",  # Recherche plus large sur le "reason"
        )

        # Étape 3 : Traiter chaque paiement pour la loterie
        for payment in payments:
            try:
                # Récupérer le character et l'utilisateur principal
                character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = character.character_ownerships.first()

                if not ownership or not ownership.user:
                    logger.warning(
                        f"No main user for character {character.character_name}."
                    )
                    continue

                user = ownership.user

                # Vérifier si un ticket existe déjà pour cet utilisateur et cette loterie
                if TicketPurchase.objects.filter(user=user, lottery=lottery).exists():
                    logger.info(
                        f"Duplicate ticket for user '{user.username}', skipping."
                    )
                    continue

                # Enregistrer la transaction de ticket
                with transaction.atomic():
                    TicketPurchase.objects.create(
                        user=user,
                        lottery=lottery,
                        character=character,
                        amount=int(payment.amount),
                        purchase_date=timezone.now(),
                    )
                    logger.info(f"Ticket registered for user '{user.username}'.")

                processed_entries += 1

            except EveCharacter.DoesNotExist:
                logger.error(
                    f"EveCharacter with ID {payment.first_party_name_id} not found."
                )
            except IntegrityError as e:
                logger.error(f"Integrity error processing payment {payment.id}: {e}")
            except Exception as e:
                logger.exception(
                    f"Unexpected error processing payment {payment.id}: {e}"
                )

    logger.info(f"Processed {processed_entries} tickets across active lotteries.")
    return f"Processed {processed_entries} tickets for all active lotteries."


def setup_tasks(sender, **kwargs):
    """
    Configure periodic tasks for all active lotteries. This ensures that wallet entries
    are periodically processed to check for ticket purchases.
    """
    active_lotteries = Lottery.objects.filter(status="active")

    # Créer ou mettre à jour une seule tâche périodique pour toutes les loteries actives
    task_name = "process_wallet_tickets_for_all_lotteries"

    # Vérifier si la tâche existe déjà pour toutes les loteries actives
    existing_task = PeriodicTask.objects.filter(name=task_name).first()

    if existing_task:
        logger.info(f"Periodic task already exists for all active lotteries.")
    else:
        # Si aucune tâche existante, créer la tâche périodique
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=5, period=IntervalSchedule.MINUTES
        )

        # Créer la tâche périodique pour traiter toutes les loteries actives
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",  # Une tâche générique pour toutes les loteries
                "interval": schedule,
                "args": json.dumps(
                    []
                ),  # Pas besoin de passer un ID spécifique, la tâche gère toutes les loteries
            },
        )
        logger.info(f"Periodic task set for processing all active lotteries.")
