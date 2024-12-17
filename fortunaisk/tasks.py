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

    # Filtrer les entrées du journal selon les critères
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=settings.payment_receiver,
        amount=settings.ticket_price,
        reason=settings.lottery_reference,  # Critère pour vérifier si la raison correspond à la référence de la loterie
    )

    for entry in journal_entries:
        try:
            # Rechercher le personnage en fonction de first_party_name_id
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)

            # Trouver l'utilisateur associé au personnage (via la table intermédiaire)
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()

            # Si un utilisateur est trouvé, insérer dans TicketPurchase
            if user:
                TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery_reference=settings.lottery_reference,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
        except EveCharacter.DoesNotExist:
            continue  # Si aucun personnage n'est trouvé pour l'entrée, passer à la suivante

    return "Processed wallet entries for ticket purchases."
