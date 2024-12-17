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
            f"Aucune entrée de portefeuille correspondante pour la loterie '{lottery.lottery_reference}'."
        )
        return f"Aucune entrée correspondante trouvée pour la loterie '{lottery.lottery_reference}'."

    # Process each matching entry
    processed_entries = 0  # Initialisation correcte
    for entry in journal_entries:
        try:
            logger.debug(
                f"Traitement de l'entrée de portefeuille ID {entry.id} pour un montant de {entry.amount}"
            )

            # Fetch EveCharacter corresponding to the first_party_name_id
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)
            logger.debug(
                f"Personnage trouvé '{character.character_name}' pour l'entrée de portefeuille {entry.id}"
            )

            # Find associated user from the character ownership table
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()
            if not user:
                logger.warning(
                    f"Aucun utilisateur associé au personnage '{character.character_name}' (ID: {character.character_id})."
                )
                continue

            # Register ticket purchase with transaction safety
            with transaction.atomic():
                TicketPurchase.objects.create(user=user, lottery=lottery)
                logger.info(
                    f"Ticket acheté par {user.username} pour la loterie '{lottery.lottery_reference}'."
                )

            processed_entries += 1

        except EveCharacter.DoesNotExist:
            logger.error(
                f"Personnage avec ID {entry.first_party_name_id} n'existe pas."
            )
        except IntegrityError:
            logger.error(
                f"Erreur d'intégrité lors de la création du ticket pour l'utilisateur {user.username}."
            )
        except Exception as e:
            logger.exception(
                f"Erreur inattendue lors du traitement de l'entrée {entry.id}: {e}"
            )
            continue

    logger.info(
        f"Processed {processed_entries} wallet entries for lottery '{lottery.lottery_reference}'."
    )
    return f"{processed_entries} entrées traitées pour la loterie '{lottery.lottery_reference}'."
