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


# Tâche pour traiter les tickets pour toutes les loteries actives
@shared_task(bind=True, base=QueueOnce)
def process_wallet_tickets(self, lottery_id):
    """
    Process ticket purchases for a specific lottery by checking wallet entries
    and recording valid purchases.

    Args:
        lottery_id (int): ID of the lottery to process.
    """
    try:
        # Étape 1 : Récupérer la loterie à partir de l'ID
        lottery = Lottery.objects.get(id=lottery_id, status="active")
    except Lottery.DoesNotExist:
        logger.error(f"Lottery {lottery_id} does not exist or is inactive.")
        return f"Lottery {lottery_id} not found."

    logger.info(f"Processing wallet entries for '{lottery.lottery_reference}'.")

    # Étape 2 : Parcourir les paiements pour la loterie spécifique
    payments = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=lottery.payment_receiver,
        amount=float(lottery.ticket_price),
        reason__startswith=f"LOTTERY-{lottery.lottery_reference}",
    )

    processed_entries = 0

    # Étape 3 : Traiter chaque paiement pour la loterie active
    for payment in payments:
        try:
            # Étape 3.1 : Récupérer le character et l'utilisateur principal
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

            # Étape 3.2 : Vérifier si le ticket existe déjà
            if TicketPurchase.objects.filter(user=user, lottery=lottery).exists():
                logger.info(f"Duplicate ticket for user '{user.username}', skipping.")
                continue

            # Étape 3.3 : Enregistrer le ticket
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
            logger.exception(f"Unexpected error processing payment {payment.id}: {e}")

    logger.info(
        f"Processed {processed_entries} tickets for '{lottery.lottery_reference}'."
    )
    return f"Processed {processed_entries} tickets for lottery '{lottery.lottery_reference}'."


def setup_tasks(sender, **kwargs):
    """
    Configure periodic tasks for all active lotteries. This ensures that wallet entries
    are periodically processed to check for ticket purchases.
    """
    active_lotteries = Lottery.objects.filter(status="active")

    for lottery in active_lotteries:
        task_name = f"process_wallet_tickets_{lottery.lottery_reference}"

        # Vérifier si la tâche existe déjà pour la loterie avant de la créer ou la mettre à jour
        existing_task = PeriodicTask.objects.filter(name=task_name).first()

        if existing_task:
            logger.info(
                f"Periodic task already exists for lottery '{lottery.lottery_reference}'."
            )
        else:
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=5, period=IntervalSchedule.MINUTES
            )

            # Créer ou mettre à jour la tâche périodique pour chaque loterie active
            PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": "fortunaisk.tasks.process_wallet_tickets",
                    "interval": schedule,
                    "args": json.dumps([lottery.id]),  # Passer l'ID de la loterie
                },
            )
            logger.info(f"Periodic task set for lottery '{lottery.lottery_reference}'.")
