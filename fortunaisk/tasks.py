# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import FortunaISKSettings, TicketPurchase


@shared_task
def process_wallet_tickets():
    """
    Traite les achats de tickets en vérifiant les entrées du wallet.
    """
    settings = FortunaISKSettings.objects.first()
    if not settings:
        return "No active FortunaISK settings found."

    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=settings.payment_receiver,
        amount=settings.ticket_price,
    )

    for entry in journal_entries:
        try:
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()
            if user:
                TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery_reference=settings.lottery_reference,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
        except EveCharacter.DoesNotExist:
            continue

    return "Processed wallet entries for ticket purchases."
