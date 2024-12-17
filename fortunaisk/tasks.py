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

# Local imports
from .models import Lottery, TicketPurchase

logger = logging.getLogger(__name__)


@shared_task(bind=True, base=QueueOnce)
def process_wallet_tickets(self, lottery_id):
    """
    Process ticket purchases by checking wallet entries and recording valid purchases.
    """
    try:
        # Step 1: Retrieve the lottery
        lottery = Lottery.objects.get(id=lottery_id, status="active")
    except Lottery.DoesNotExist:
        logger.error(f"Lottery {lottery_id} does not exist or is inactive.")
        return f"Lottery {lottery_id} not found."

    logger.info(f"Processing wallet entries for '{lottery.lottery_reference}'.")

    # Step 2: Fetch wallet entries matching lottery
    payments = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=lottery.payment_receiver,
        amount=float(lottery.ticket_price),
        reason__startswith=f"LOTTERY-{lottery.lottery_reference}",
    )

    processed_entries = 0

    # Step 3: Process wallet entries
    for payment in payments:
        try:
            # Retrieve EveCharacter and main user
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

            # Avoid duplicate tickets
            if TicketPurchase.objects.filter(user=user, lottery=lottery).exists():
                logger.info(f"Duplicate ticket for user '{user.username}', skipping.")
                continue

            # Register the ticket purchase
            with transaction.atomic():
                TicketPurchase.objects.create(
                    user=user,
                    lottery=lottery,
                    character=character,
                    amount=int(payment.amount),
                    purchase_date=timezone.now(),
                )
                logger.info(
                    f"Ticket registered: User '{user.username}' for '{lottery.lottery_reference}'."
                )

            processed_entries += 1

        except EveCharacter.DoesNotExist:
            logger.error(
                f"EveCharacter with ID {payment.first_party_name_id} not found."
            )
        except IntegrityError as e:
            logger.error(f"Database error processing payment {payment.id}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error processing payment {payment.id}: {e}")

    logger.info(
        f"Processed {processed_entries} tickets for '{lottery.lottery_reference}'."
    )
    return f"Processed {processed_entries} tickets for '{lottery.lottery_reference}'."
