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

# Configuration du logger pour Celery
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# Tâche pour traiter les paiements de tickets pour toutes les loteries actives
@shared_task(bind=True)
def process_wallet_tickets(self):
    logger.info("Processing wallet entries for active lotteries.")

    # Logique de la tâche pour traiter les tickets de loterie
    active_lotteries = Lottery.objects.filter(status="active")
    if not active_lotteries.exists():
        logger.info("No active lotteries found.")
        return "No active lotteries to process."

    processed_entries = 0
    for lottery in active_lotteries:
        logger.info(
            f"Processing lottery: {lottery.id}, reference: {lottery.lottery_reference}"
        )

        # Utilisation directe de la référence de la loterie sans ajout de 'LOTTERY-'
        reason_filter = lottery.lottery_reference
        logger.info(
            f"Filtering payments with: second_party_name_id={lottery.payment_receiver}, amount={lottery.ticket_price}, reason contains '{reason_filter}'"
        )

        payments = CorporationWalletJournalEntry.objects.filter(
            second_party_name_id=lottery.payment_receiver,
            amount=lottery.ticket_price,
            reason__contains=reason_filter,
        )

        # Ajout d'un log pour afficher les paiements trouvés
        logger.info(f"Found {payments.count()} payments for lottery: {lottery.id}")

        if not payments.exists():
            logger.info(f"No payments found for lottery: {lottery.id}")
            continue

        for payment in payments:
            logger.info(
                f"Processing payment: {payment.id}, amount: {payment.amount}, reason: {payment.reason}"
            )
            try:
                character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = character.character_ownerships.first()
                if not ownership or not ownership.user:
                    logger.warning(
                        f"No main user for character {character.character_name} (ID: {character.character_id})."
                    )
                    continue

                user = ownership.user
                user_profile = user.profile
                if user_profile.main_character_id != character.id:
                    logger.warning(
                        f"Character {character.character_name} (ID: {character.character_id}) is not the main character for user {user.username}."
                    )
                    continue

                if TicketPurchase.objects.filter(user=user, lottery=lottery).exists():
                    logger.info(
                        f"Duplicate ticket for user '{user.username}', skipping."
                    )
                    continue

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
    task_name = "process_wallet_tickets_for_all_lotteries"
    schedule, created = IntervalSchedule.objects.get_or_create(
        every=5,
        period=IntervalSchedule.MINUTES,
    )
    PeriodicTask.objects.update_or_create(
        name=task_name,
        defaults={
            "task": "fortunaisk.tasks.process_wallet_tickets",
            "interval": schedule,
            "args": json.dumps([]),
        },
    )
    if created:
        logger.info(f"Created new periodic task: {task_name}")
    else:
        logger.info(f"Updated existing periodic task: {task_name}")
