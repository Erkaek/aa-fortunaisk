# fortunaisk/views.py

# Standard Library
import logging

# Third Party
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User  # Standard Django user model
from django.db.models import Count
from django.shortcuts import render

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from .models import Lottery, TicketPurchase, Winner

logger = logging.getLogger(__name__)


@login_required
def lottery(request):
    current_lottery = Lottery.objects.filter(status="active").first()
    if not current_lottery:
        return render(
            request, "fortunaisk/lottery.html", {"message": "No active lottery."}
        )

    # Retrieve corporation name if Payment Receiver is a corporation ID
    corporation_name = None
    if current_lottery.payment_receiver.isdigit():  # Check if Payment Receiver is an ID
        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=int(current_lottery.payment_receiver)
            )
            corporation_name = corporation.corporation_name
        except EveCorporationInfo.DoesNotExist:
            corporation_name = "Unknown Corporation"

    has_ticket = TicketPurchase.objects.filter(
        user=request.user,
        lottery=current_lottery,
    ).exists()

    instructions = (
        f"Send {current_lottery.ticket_price} ISK to {corporation_name or current_lottery.payment_receiver} with reference '{current_lottery.lottery_reference}' to participate."
        if current_lottery
        else "No lottery is currently available."
    )

    context = {
        "current_lottery": current_lottery,
        "corporation_name": corporation_name,
        "has_ticket": has_ticket,
        "instructions": instructions,
    }

    return render(request, "fortunaisk/lottery.html", context)


@login_required
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
def ticket_purchases(request):
    current_lottery = Lottery.objects.filter(status="active").first()
    if not current_lottery:
        return render(
            request,
            "fortunaisk/ticket_purchases.html",
            {"purchases": [], "message": "No active lottery."},
        )

    # Filter journal entries
    journal_entries = CorporationWalletJournalEntry.objects.filter(
        second_party_name_id=current_lottery.payment_receiver,
        amount=current_lottery.ticket_price,
        reason=f"LOTTERY-{current_lottery.lottery_reference}",  # Ensure format matches
    )

    if not journal_entries.exists():
        logger.info("No journal entries found matching the criteria.")
        return render(
            request,
            "fortunaisk/ticket_purchases.html",
            {
                "purchases": [],
                "message": "No matching journal entries found.",
            },
        )

    purchases = []
    for entry in journal_entries:
        try:
            # Log processed journal entry
            logger.debug(
                f"Processing journal entry {entry.id} for character ID {entry.first_party_name_id}"
            )

            # Find character
            character = EveCharacter.objects.get(character_id=entry.first_party_name_id)

            # Log found character
            logger.debug(
                f"Found character: {character.character_name} (ID: {character.character_id})"
            )

            # Find user associated with character
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()

            if user:
                logger.debug(f"Found user: {user.username}")
                # Create or get a ticket
                purchase, created = TicketPurchase.objects.get_or_create(
                    user=user,
                    character=character,
                    lottery=current_lottery,
                    defaults={"amount": entry.amount, "date": entry.date},
                )
                purchases.append(purchase)

                # Log if ticket was created or already existed
                if created:
                    logger.info(f"Ticket purchase created for user: {user.username}")
                else:
                    logger.info(
                        f"Ticket purchase already exists for user: {user.username}"
                    )
            else:
                logger.warning(
                    f"No user found for character: {character.character_name}"
                )

        except EveCharacter.DoesNotExist:
            logger.error(f"Character with ID {entry.first_party_name_id} not found.")
            continue  # Skip to next entry if character does not exist

    return render(
        request,
        "fortunaisk/ticket_purchases.html",
        {
            "purchases": purchases,
            "lottery_reference": current_lottery.lottery_reference,
        },
    )


@permission_required("fortunaisk.admin", raise_exception=True)
def select_winner(request, lottery_id):
    try:
        lottery = Lottery.objects.get(id=lottery_id, is_active=True)
    except Lottery.DoesNotExist:
        messages.error(request, "Loterie non trouvée ou inactivée.")
        return render(request, "fortunaisk/lottery.html")

    participants = User.objects.filter(ticketpurchase__lottery=lottery).annotate(
        ticket_count=Count("ticketpurchase")
    )
    if not participants.exists():
        messages.info(request, "Aucun participant pour cette loterie.")
        return render(request, "fortunaisk/lottery.html")

    winner = participants.order_by("?").first()
    lottery.winner = winner
    lottery.is_active = False
    lottery.save()

    messages.success(
        request, f"Félicitations à {winner.username} pour avoir gagné la loterie!"
    )
    return render(request, "fortunaisk/winner.html", {"winner": winner})


@login_required
def winner_list(request):
    winners = Winner.objects.all().select_related("character", "ticket__lottery")
    return render(
        request,
        "fortunaisk/winner_list.html",
        {"winners": winners},
    )


@permission_required("fortunaisk.admin", raise_exception=True)
def admin_dashboard(request):
    current_lottery = Lottery.objects.filter(status="active").first()
    total_tickets = TicketPurchase.objects.filter(
        lottery=current_lottery if current_lottery else None
    ).count()

    past_lotteries = Lottery.objects.filter(status="completed").order_by("-end_date")

    return render(
        request,
        "fortunaisk/admin.html",  # Ensure the template path is correct
        {
            "current_lottery": current_lottery,
            "total_tickets": total_tickets,
            "past_lotteries": past_lotteries,
        },
    )


@login_required
def user_dashboard(request):
    user = request.user
    ticket_purchases = TicketPurchase.objects.filter(user=user).select_related(
        "lottery"
    )
    winnings = Winner.objects.filter(ticket__user=user).select_related(
        "ticket__lottery", "character"
    )

    context = {
        "ticket_purchases": ticket_purchases,
        "winnings": winnings,
    }

    return render(request, "fortunaisk/user_dashboard.html", context)


@login_required
def lottery_history(request):
    past_lotteries = Lottery.objects.filter(status="completed").order_by("-end_date")
    winners = Winner.objects.filter(ticket__lottery__in=past_lotteries)
    return render(
        request,
        "fortunaisk/lottery_history.html",
        {"past_lotteries": past_lotteries, "winners": winners},
    )
