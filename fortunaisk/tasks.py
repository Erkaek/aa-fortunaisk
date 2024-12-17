# Standard Library
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.db import transaction

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
        return f"No matching wallet entries found for lottery '{lottery.lottery_reference}'."

    # Process each matching entry
    processed_entries = 0
    for entry in journal_entries:
        try:
            logger.debug(
                f"Processing wallet entry ID {entry.id} for amount {entry.amount}"
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
                    f"No user associated with character '{character.character_name}' (ID: {character.character_id})."
                )
                continue

            # Register ticket purchase with transaction safety
            with transaction.atomic():
                _, created = TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery=lottery,
                    defaults={"amount": entry.amount, "date": entry.date},
                )

                if created:
                    logger.info(
                        f"Ticket purchase recorded for user '{user.username}' (Character: {character.character_name})."
                    )
                    processed_entries += 1
                else:
                    logger.info(
                        f"Duplicate ticket purchase for user '{user.username}', skipping."
                    )

        except EveCharacter.DoesNotExist:
            logger.error(
                f"EveCharacter with ID {entry.first_party_name_id} does not exist. Skipping entry {entry.id}."
            )
        except Exception as e:
            logger.exception(f"Error processing wallet entry {entry.id}: {e}")
            continue

    logger.info(
        f"Processed {processed_entries} wallet entries for lottery '{lottery.lottery_reference}'."
    )
    return f"Processed {processed_entries} wallet entries for lottery '{lottery.lottery_reference}'."
