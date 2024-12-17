# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.utils import timezone

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
        reason="LOTTERY-"
        + settings.lottery_reference,  # Critère pour vérifier si la raison correspond à la référence de la loterie
    )

    if not journal_entries.exists():
        return "No journal entries matching the criteria."

    for entry in journal_entries:
        try:
            # Log les informations de l'entrée du journal
            print(
                f"Processing journal entry: {entry.id}, first_party_name_id: {entry.first_party_name_id}, second_party_name_id: {entry.second_party_name_id}, amount: {entry.amount}, reason: {entry.reason}"
            )

            # Rechercher le personnage en fonction de first_party_name_id
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)

            # Log les informations du personnage trouvé
            print(
                f"Found character: {character.character_name} (ID: {character.character_id})"
            )

            # Trouver l'utilisateur associé au personnage (via la table intermédiaire)
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()

            # Log l'utilisateur trouvé
            if user:
                print(f"Found user: {user.username}")
            else:
                print(f"No user found for character: {character.character_name}")

            # Si un utilisateur est trouvé, insérer dans TicketPurchase
            if user:
                ticket, created = TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery_reference=settings.lottery_reference,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
                if created:
                    print(
                        f"Created TicketPurchase: {ticket.id} for user {user.username}"
                    )
                else:
                    print(f"TicketPurchase already exists for user {user.username}")
        except EveCharacter.DoesNotExist:
            print(f"Character with ID {entry.first_party_name_id} does not exist.")
            continue  # Si aucun personnage n'est trouvé pour l'entrée, passer à la suivante

    return "Processed wallet entries for ticket purchases."
