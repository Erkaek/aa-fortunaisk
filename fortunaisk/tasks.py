# Standard Library
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.db import IntegrityError, transaction
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.tasks import QueueOnce

from .models import Lottery, TicketPurchase

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=QueueOnce)
def process_wallet_tickets(self, lottery_id):
    """
    Process ticket purchases for a specific lottery by checking wallet entries
    and recording valid ticket purchases.

    Args:
        lottery_id (int): ID of the lottery to process.
    """
    try:
        # Step 1: Retrieve the lottery
        lottery = Lottery.objects.get(id=lottery_id, status="active")
    except Lottery.DoesNotExist:
        logger.error(f"Lottery with ID {lottery_id} does not exist or is inactive.")
        return f"Lottery with ID {lottery_id} not found."

    logger.info(f"Processing wallet entries for lottery '{lottery.lottery_reference}'.")

    # Step 2: Fetch relevant wallet entries
    payments = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=lottery.payment_receiver,
        amount__exact=float(lottery.ticket_price),
        reason__startswith=f"LOTTERY-{lottery.lottery_reference}",
    )

    # Step 3: Group payments by reason
    payment_dict = {}
    for payment in payments:
        reason = payment.reason.strip()
        if reason not in payment_dict:
            payment_dict[reason] = []
        payment_dict[reason].append(payment)

    # Step 4: Process each ticket purchase
    processed_entries = 0
    for reason, payment_list in payment_dict.items():
        try:
            # Extract EveCharacter from the first valid payment
            first_payment = payment_list[0]
            character = EveCharacter.objects.get(
                character_id=first_payment.first_party_name_id
            )
            user = character.character_ownerships.first().user

            # Ensure the user and ticket are valid
            if not user:
                logger.warning(
                    f"No user found for character '{character.character_name}'."
                )
                continue

            # Check if a ticket already exists to avoid duplicates
            if TicketPurchase.objects.filter(user=user, lottery=lottery).exists():
                logger.info(f"Duplicate ticket for user '{user.username}' skipped.")
                continue

            # Create ticket purchase transaction
            with transaction.atomic():
                TicketPurchase.objects.create(
                    user=user,
                    lottery=lottery,
                    character=character,
                    amount=lottery.ticket_price,
                    purchase_date=timezone.now(),
                )
                logger.info(f"Ticket registered for user '{user.username}'.")

            processed_entries += 1

        except EveCharacter.DoesNotExist:
            logger.error(
                f"Character with ID '{first_payment.first_party_name_id}' does not exist."
            )
        except IntegrityError as e:
            logger.error(f"Integrity error while processing '{reason}': {e}")
        except Exception as e:
            logger.exception(f"Unexpected error processing reason '{reason}': {e}")

    logger.info(
        f"Processed {processed_entries} ticket entries for lottery '{lottery.lottery_reference}'."
    )
    return f"{processed_entries} entries processed for lottery '{lottery.lottery_reference}'."


def setup_tasks(sender, **kwargs):
    """
    Configure tasks for active lotteries. Placeholder function.
    """
    active_lotteries = Lottery.objects.filter(status="active")
    for lottery in active_lotteries:
        logger.info(f"Setting up tasks for lottery: {lottery.lottery_reference}")
