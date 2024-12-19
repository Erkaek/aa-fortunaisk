# fortunaisk/views.py

# Standard Library
import logging

# Third Party
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

from .forms import LotterySettingsForm
from .models import Lottery, LotterySettings, TicketPurchase, Winner

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
    if str(current_lottery.payment_receiver).isdigit():
        corporation_name = (
            EveCorporationInfo.objects.filter(
                corporation_id=int(current_lottery.payment_receiver)
            )
            .values_list("corporation_name", flat=True)
            .first()
            or "Unknown Corporation"
        )

    has_ticket = TicketPurchase.objects.filter(
        user=request.user, lottery=current_lottery
    ).exists()
    instructions = (
        f"Send {current_lottery.ticket_price} ISK to {corporation_name or current_lottery.payment_receiver} "
        f"with reference '{current_lottery.lottery_reference}' to participate."
    )

    return render(
        request,
        "fortunaisk/lottery.html",
        {
            "current_lottery": current_lottery,
            "corporation_name": corporation_name,
            "has_ticket": has_ticket,
            "instructions": instructions,
        },
    )


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
        reason=f"LOTTERY-{current_lottery.lottery_reference}",
    )

    if not journal_entries.exists():
        logger.info("No journal entries found matching the criteria.")
        return render(
            request,
            "fortunaisk/ticket_purchases.html",
            {"purchases": [], "message": "No matching journal entries found."},
        )

    # Cache for EveCharacters to reduce redundant queries
    character_cache = {}
    purchases = []

    for entry in journal_entries:
        try:
            # Use cache for character lookup
            character_id = entry.first_party_name_id
            if character_id not in character_cache:
                character_cache[character_id] = EveCharacter.objects.get(
                    character_id=character_id
                )

            character = character_cache[character_id]

            # Find user associated with the character
            user = User.objects.filter(
                character_ownerships__character=character
            ).first()
            if not user:
                logger.warning(
                    f"No user found for character: {character.character_name}"
                )
                continue

            # Create or get a ticket
            purchase, created = TicketPurchase.objects.get_or_create(
                user=user,
                lottery=current_lottery,
                character=character,
                defaults={"amount": entry.amount, "purchase_date": entry.date},
            )
            purchases.append(purchase)

            logger.info(
                f"Ticket purchase {'created' if created else 'already exists'} for user: {user.username}"
            )
        except EveCharacter.DoesNotExist:
            logger.warning(f"Character with ID {character_id} not found.")
            continue

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
    lottery = get_object_or_404(Lottery, id=lottery_id, status="active")
    participants = User.objects.filter(ticketpurchase__lottery=lottery).annotate(
        ticket_count=Count("ticketpurchase")
    )

    if not participants.exists():
        messages.info(request, "Aucun participant pour cette loterie.")
        return render(request, "fortunaisk/lottery.html")

    winner = participants.order_by("?").first()
    lottery.winner = winner
    lottery.status = "completed"
    lottery.save()

    messages.success(
        request, f"Félicitations à {winner.username} pour avoir gagné la loterie!"
    )
    return render(request, "fortunaisk/winner.html", {"winner": winner})


@login_required
def winner_list(request):
    winners = Winner.objects.select_related("character", "ticket__lottery")
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})


@permission_required("fortunaisk.admin", raise_exception=True)
def admin_dashboard(request):
    current_lottery = Lottery.objects.filter(status="active").first()
    total_tickets = (
        TicketPurchase.objects.filter(lottery=current_lottery).count()
        if current_lottery
        else 0
    )
    past_lotteries = Lottery.objects.filter(status="completed").order_by("-end_date")

    # Configuration Payment Receiver
    settings, _ = LotterySettings.objects.get_or_create()
    if request.method == "POST":
        form = LotterySettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            return redirect("fortunaisk:admin_dashboard")
    else:
        form = LotterySettingsForm(instance=settings)

    return render(
        request,
        "fortunaisk/admin.html",
        {
            "current_lottery": current_lottery,
            "total_tickets": total_tickets,
            "past_lotteries": past_lotteries,
            "form": form,
        },
    )


@login_required
def user_dashboard(request):
    user = request.user
    ticket_purchases = TicketPurchase.objects.filter(user=user).select_related(
        "lottery", "character"
    )
    winnings = Winner.objects.filter(ticket__user=user).select_related(
        "ticket__lottery", "character"
    )

    return render(
        request,
        "fortunaisk/user_dashboard.html",
        {"ticket_purchases": ticket_purchases, "winnings": winnings},
    )


@login_required
def lottery_history(request):
    past_lotteries = Lottery.objects.filter(status="completed").order_by("-end_date")
    winners = Winner.objects.filter(ticket__lottery__in=past_lotteries).select_related(
        "character", "ticket__lottery"
    )

    return render(
        request,
        "fortunaisk/lottery_history.html",
        {"past_lotteries": past_lotteries, "winners": winners},
    )


@login_required
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
def lottery_participants(request, lottery_id):
    """
    Vue pour afficher les participants d'une loterie.
    """
    lottery = get_object_or_404(Lottery, id=lottery_id)
    participants = TicketPurchase.objects.filter(lottery=lottery).select_related(
        "user", "character"
    )

    return render(
        request,
        "fortunaisk/lottery_participants.html",
        {"lottery": lottery, "participants": participants},
    )
