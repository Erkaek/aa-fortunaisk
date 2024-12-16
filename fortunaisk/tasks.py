# Standard Library
from datetime import timedelta

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.utils.timezone import now

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter
from allianceauth.services.hooks import get_hooks

from .models import FortunaISKSettings, TicketPurchase


@shared_task(bind=True, name="fortunaisk.process_ticket_purchases")
def process_ticket_purchases(self):
    """
    Tâche Celery qui vérifie les transactions ISK et remplit la table TicketPurchase.
    """
    settings = FortunaISKSettings.objects.first()
    if not settings:
        self.logger.info("No active lottery settings found.")
        return

    self.logger.info(
        f"Running ticket purchase check for lottery: {settings.lottery_reference}"
    )

    # Récupérer les transactions où Payment Receiver et prix du ticket correspondent
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name=settings.payment_receiver,
        amount=settings.ticket_price,
        date__gte=now() - timedelta(days=30),  # Vérifie sur les 30 derniers jours
    )

    count = 0
    for entry in journal_entries:
        try:
            character = EveCharacter.objects.get(character_id=entry.first_party_id)
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()

            if user:
                # Insérer ou mettre à jour dans TicketPurchase
                TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery_reference=settings.lottery_reference,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
                count += 1
        except EveCharacter.DoesNotExist:
            continue

    self.logger.info(f"Processed {count} ticket purchases.")
