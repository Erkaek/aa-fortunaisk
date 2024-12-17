# fortunaisk/tasks.py

# Standard Library
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import Lottery, TicketPurchase

logger = logging.getLogger(__name__)


@shared_task
def process_wallet_tickets(lottery_id):
    """
    Process ticket purchases by checking wallet entries for a specific lottery.
    """
    try:
        lottery = Lottery.objects.get(id=lottery_id)
    except Lottery.DoesNotExist:
        logger.error(f"Lottery with ID {lottery_id} does not exist.")
        return "Lottery not found."

    if lottery.status != "active":
        logger.info(f"Lottery {lottery.lottery_reference} is not active.")
        return "Lottery not active."

    # Filter journal entries based on criteria
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=lottery.payment_receiver,
        amount=lottery.ticket_price,
        reason__startswith=f"LOTTERY-{lottery.lottery_reference}",
    )

    if not journal_entries.exists():
        logger.info("No journal entries matching the criteria.")
        return "No journal entries matching the criteria."

    for entry in journal_entries:
        try:
            # Log journal entry information
            logger.debug(
                f"Processing journal entry: {entry.id}, first_party_name_id: {entry.first_party_name_id}, "
                f"second_party_name_id: {entry.second_party_name_id}, amount: {entry.amount}, reason: {entry.reason}"
            )

            # Find character based on first_party_name_id
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)

            # Log found character
            logger.debug(
                f"Found character: {character.character_name} (ID: {character.character_id})"
            )

            # Find user associated with character via intermediary table
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()

            # Log found user
            if user:
                logger.debug(f"Found user: {user.username}")
            else:
                logger.warning(
                    f"No user found for character: {character.character_name}"
                )

            # If user found, insert into TicketPurchase
            if user:
                ticket, created = TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery=lottery,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
                if created:
                    logger.info(
                        f"Ticket purchase created: {ticket.id} for user {user.username}"
                    )
                else:
                    logger.info(
                        f"Ticket purchase already exists for user {user.username}"
                    )
        except EveCharacter.DoesNotExist:
            logger.error(
                f"Character with ID {entry.first_party_name_id} does not exist."
            )
            continue  # Skip to next entry if character not found

    return f"Wallet entries processed for lottery {lottery.lottery_reference}."
