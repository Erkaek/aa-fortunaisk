# Standard Library
from random import choice

# Third Party
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User  # Modèle utilisateur standard de Django
from django.http import JsonResponse
from django.shortcuts import render

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import FortunaISKSettings, TicketPurchase, Winner


@login_required
def lottery(request):
    settings = FortunaISKSettings.objects.first()
    if not settings:
        return render(
            request, "fortunaisk/lottery.html", {"message": "No active lottery."}
        )

    has_ticket = TicketPurchase.objects.filter(
        user=request.user,
        lottery_reference=settings.lottery_reference,
    ).exists()

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
def ticket_purchases(request):
    settings = FortunaISKSettings.objects.first()
    if not settings:
        return render(
            request,
            "fortunaisk/ticket_purchases.html",
            {"purchases": [], "message": "No active lottery."},
        )

    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name=settings.payment_receiver,
        amount=settings.ticket_price,
    )

    purchases = []
    for entry in journal_entries:
        try:
            character = EveCharacter.objects.get(character_id=entry.first_party_id)
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()
            if user:
                purchase, created = TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery_reference=settings.lottery_reference,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
                purchases.append(purchase)
        except EveCharacter.DoesNotExist:
            continue

    return render(
        request,
        "fortunaisk/ticket_purchases.html",
        {"purchases": purchases, "lottery_reference": settings.lottery_reference},
    )


@permission_required("fortunaisk.admin")
def select_winner(request):
    settings = FortunaISKSettings.objects.first()
    if not settings:
        return JsonResponse({"error": "No active lottery."}, status=400)

    participants = TicketPurchase.objects.filter(
        lottery_reference=settings.lottery_reference
    )
    if not participants.exists():
        return JsonResponse({"error": "No participants found."}, status=400)

    winner = choice(participants)
    Winner.objects.create(character=winner.character, ticket=winner)

    return JsonResponse(
        {
            "winner": {
                "user": winner.user.username,
                "character": winner.character.character_name,
                "lottery_reference": winner.lottery_reference,
                "date": winner.date.strftime("%Y-%m-%d %H:%M:%S"),
            }
        }
    )


@login_required
def winner_list(request):
    winners = Winner.objects.all().select_related("character", "ticket")
    return render(
        request,
        "fortunaisk/winner_list.html",
        {"winners": winners},
    )


def admin_dashboard(request):
    settings = FortunaISKSettings.objects.first()
    total_tickets = TicketPurchase.objects.filter(
        lottery_reference=settings.lottery_reference if settings else None
    ).count()

    return render(
        request,
        "fortunaisk/admin.html",  # Assurez-vous que le chemin du template correspond
        {
            "settings": settings,
            "total_tickets": total_tickets,
        },
    )
