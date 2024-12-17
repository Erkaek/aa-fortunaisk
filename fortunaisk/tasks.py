# Standard Library
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

# Local imports
from .models import Lottery, TicketPurchase

logger = logging.getLogger(__name__)


@shared_task
def process_wallet_tickets(lottery_id):
    """
    Process ticket purchases by checking wallet entries for a specific lottery.
    Scans CorporationWalletJournalEntry for matching ISK transactions
    and records ticket purchases accordingly.

    Args:
        lottery_id (int): ID of the lottery to process.

    Returns:
        str: Result of the processing.
    """
    try:
        # Retrieve the lottery
        lottery = Lottery.objects.get(id=lottery_id)
    except Lottery.DoesNotExist:
        logger.error(f"Lottery with ID {lottery_id} does not exist.")
        return f"Lottery with ID {lottery_id} not found."

    if lottery.status != "active":
        logger.info(f"Lottery '{lottery.lottery_reference}' is not active.")
        return f"Lottery '{lottery.lottery_reference}' is not active."

    logger.info(f"Processing wallet entries for lottery '{lottery.lottery_reference}'.")

    # Fetch matching wallet journal entries
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=lottery.payment_receiver,
        amount=lottery.ticket_price,
        reason__startswith=f"LOTTERY-{lottery.lottery_reference}",
    )

    if not journal_entries.exists():
        logger.info(
            f"No matching wallet entries for lottery '{lottery.lottery_reference}'."
        )
        return f"No matching entries found for lottery '{lottery.lottery_reference}'."

    # Process each matching entry
    processed_entries = 0
    for entry in journal_entries:
        try:
            logger.debug(
                f"Processing wallet entry ID {entry.id} with amount {entry.amount}"
            )

            # Fetch EveCharacter corresponding to the first_party_name_id
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)
            logger.debug(
                f"Found character '{character.character_name}' for wallet entry {entry.id}"
            )

            # Find associated user from the character ownership table
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()
            if not user:
                logger.warning(
                    f"No user associated with character '{character.character_name}' "
                    f"(ID: {character.character_id})."
                )
                continue

            # Register ticket purchase with transaction safety
            with transaction.atomic():
                TicketPurchase.objects.create(
                    user=user, lottery=lottery, character=character, amount=entry.amount
                )
                logger.info(
                    f"Ticket purchased by {user.username} for lottery '{lottery.lottery_reference}'."
                )

            processed_entries += 1

        except EveCharacter.DoesNotExist:
            logger.error(f"Character with ID {entry.first_party_name_id} does not exist.")
        except IntegrityError as e:
            logger.error(f"Integrity error: {e}")
        except Exception as e:
            logger.exception(
                f"Unexpected error while processing wallet entry {entry.id}: {e}"
            )
            continue

    logger.info(
        f"Processed {processed_entries} wallet entries for lottery '{lottery.lottery_reference}'."
    )
    return f"{processed_entries} entries processed for lottery '{lottery.lottery_reference}'."


def setup_tasks(sender, **kwargs):
    """
    Placeholder for task setup, e.g., initializing periodic tasks for active lotteries.
    """
    active_lotteries = Lottery.objects.filter(status="active")
    for lottery in active_lotteries:
        logger.info(f"Setting up tasks for lottery: {lottery.lottery_reference}")
