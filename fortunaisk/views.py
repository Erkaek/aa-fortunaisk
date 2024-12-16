# Third Party
from authentication.models import OwnershipRecord
from corptools.models import CorporationWalletJournalEntry

# Django
from django.db.models import Q
from django.shortcuts import render

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import FortunaISKSettings


@login_required
def lottery(request):
    settings = FortunaISKSettings.objects.first()
    has_ticket = Ticket.objects.filter(
        character__character_ownership__user=request.user
    ).exists()

    # Instructions à afficher uniquement si une loterie est en cours
    instructions = (
        f"Send {settings.ticket_price} ISK to {settings.payment_receiver} with reference '{settings.lottery_reference}' to participate."
        if settings
        else "No lottery is currently available."
    )

    context = {
        "settings": settings,
        "has_ticket": has_ticket,
        "instructions": instructions,
    }

    return render(request, "fortunaisk/lottery.html", context)


@login_required
def winner_list(request):
    winners = Winner.objects.all()
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})


@permission_required("fortunaisk.admin")
def admin_dashboard(request):
    return render(request, "fortunaisk/admin.html")


@login_required
def ticket_purchases(request):
    # Récupérer la loterie en cours
    settings = FortunaISKSettings.objects.first()
    if not settings:
        return render(
            request,
            "fortunaisk/ticket_purchases.html",
            {"purchases": [], "message": "No active lottery."},
        )

    # Filtrer les transactions correspondant au Payment Receiver
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name=settings.payment_receiver,
        amount=settings.ticket_price,
    )

    # Lier les transactions à un utilisateur Auth
    purchases = []
    for entry in journal_entries:
        # Trouver l'ID du personnage correspondant au first_party_name_id
        try:
            character = EveCharacter.objects.get(character_id=entry.first_party_id)
            # Trouver l'utilisateur Auth associé au personnage
            ownership = OwnershipRecord.objects.filter(character=character).first()
            if ownership:
                purchases.append(
                    {
                        "user": ownership.user,
                        "character": character.character_name,
                        "amount": entry.amount,
                        "date": entry.date,
                        "reference": settings.lottery_reference,
                    }
                )
        except EveCharacter.DoesNotExist:
            continue

    return render(
        request,
        "fortunaisk/ticket_purchases.html",
        {"purchases": purchases, "lottery_reference": settings.lottery_reference},
    )
