# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import FortunaISKSettings, TicketPurchase


@shared_task
def process_ticket_purchases():
    """
    Traite les achats de tickets en analysant les entrées de wallet.
    """
    settings = FortunaISKSettings.objects.first()
    if not settings:
        return "No active lottery settings found."

    # Récupérer les entrées de wallet correspondantes
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name=settings.payment_receiver,
        amount=settings.ticket_price,
    )

    processed_count = 0
    for entry in journal_entries:
        try:
            character = EveCharacter.objects.get(character_id=entry.first_party_id)
            TicketPurchase.objects.get_or_create(
                user=character.character_ownership.user,
                character=character,
                lottery_reference=settings.lottery_reference,
                defaults={"amount": entry.amount, "date": timezone.now()},
            )
            processed_count += 1
        except EveCharacter.DoesNotExist:
            continue

    return f"Processed {processed_count} ticket purchases."
