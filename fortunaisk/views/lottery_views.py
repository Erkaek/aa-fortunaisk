# fortunaisk/views/lottery_views.py

# Standard Library
import logging

# Django
from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import (  # type: ignore
    login_required,
    permission_required,
)
from django.core.paginator import Paginator  # type: ignore
from django.db.models import Count  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore
from django.utils.translation import gettext as _  # type: ignore

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo  # type: ignore

# fortunaisk
from fortunaisk.forms import LotteryCreateForm
from fortunaisk.models import Lottery, TicketAnomaly, TicketPurchase, Winner
from fortunaisk.notifications import (  # Importations ajoutées
    send_alliance_auth_notification,
    send_discord_notification,
)

logger = logging.getLogger(__name__)


@login_required
def lottery(request):
    active_lotteries = (
        Lottery.objects.filter(status="active")
        # .select_related("payment_receiver")  # Suppression de cette ligne
        .prefetch_related("ticket_purchases")
    )
    lotteries_info = []

    # Précharger les noms des corporations pour minimiser les requêtes
    corp_ids = active_lotteries.values_list("payment_receiver", flat=True)
    corporations = EveCorporationInfo.objects.filter(corporation_id__in=corp_ids)
    corp_map = {corp.corporation_id: corp.corporation_name for corp in corporations}

    # Précompter les tickets de l'utilisateur
    user_ticket_counts = (
        TicketPurchase.objects.filter(user=request.user, lottery__in=active_lotteries)
        .values("lottery")
        .annotate(count=Count("id"))
    )
    user_ticket_map = {item["lottery"]: item["count"] for item in user_ticket_counts}

    for lot in active_lotteries:
        corp_name = corp_map.get(lot.payment_receiver, "Unknown Corporation")

        user_ticket_count = user_ticket_map.get(lot.id, 0)
        has_ticket = user_ticket_count > 0

        instructions = _(
            "To participate, send {ticket_price} ISK to {corp_name} with the reference '{lottery_reference}' in the payment description."
        ).format(
            ticket_price=lot.ticket_price,
            corp_name=corp_name,
            lottery_reference=lot.lottery_reference,
        )

        lotteries_info.append(
            {
                "lottery": lot,
                "corporation_name": corp_name,
                "has_ticket": has_ticket,
                "instructions": instructions,
                "user_ticket_count": user_ticket_count,
            }
        )

    return render(
        request,
        "fortunaisk/lottery.html",
        {"active_lotteries": lotteries_info},
    )


@login_required
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
def ticket_purchases(request):
    current_lotteries = Lottery.objects.filter(status="active")
    purchases = (
        TicketPurchase.objects.filter(lottery__in=current_lotteries)
        .select_related("user", "character", "lottery")
        .order_by("-purchase_date")
    )
    paginator = Paginator(purchases, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/ticket_purchases.html", {"page_obj": page_obj})


@login_required
@permission_required("fortunaisk.view_winner", raise_exception=True)
def winner_list(request):
    winners = Winner.objects.select_related(
        "character", "ticket__user", "ticket__lottery"
    ).order_by("-won_at")
    paginator = Paginator(winners, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/winner_list.html", {"page_obj": page_obj})


@login_required
def lottery_history(request):
    # Exemple : toutes les loteries complétées ou annulées
    past_lotteries = (
        Lottery.objects.exclude(status="active")
        # .select_related("payment_receiver")  # Suppression de cette ligne
        .prefetch_related("winners")
    )
    paginator = Paginator(past_lotteries, 6)  # 6 par page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "past_lotteries": page_obj,
        "page_obj": page_obj,
    }

    return render(
        request,
        "fortunaisk/lottery_history.html",
        context,  # Utilisation de la variable context
    )


@login_required
@permission_required("fortunaisk.add_lottery", raise_exception=True)
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            lottery = form.save(commit=False)
            lottery.modified_by = request.user  # Définir l'utilisateur actuel
            lottery.save()
            messages.success(request, "Lottery created successfully.")
            return redirect("fortunaisk:lottery")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LotteryCreateForm()

    winner_count = form.instance.winner_count or 1
    try:
        winner_count = int(winner_count)
        if winner_count < 1:
            winner_count = 1
    except (ValueError, TypeError):
        winner_count = 1

    distribution_range = range(winner_count)

    return render(
        request,
        "fortunaisk/lottery_form.html",
        {
            "form": form,
            "is_auto_lottery": False,
            "distribution_range": distribution_range,
        },
    )


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_detail(request, lottery_id):
    lottery = get_object_or_404(Lottery, id=lottery_id)
    participants = lottery.ticket_purchases.select_related("user", "character").all()
    anomalies = (
        TicketAnomaly.objects.filter(lottery=lottery).select_related("user").all()
    )
    winners = (
        Winner.objects.filter(ticket__lottery=lottery)
        .select_related("ticket__user", "character")
        .all()
    )

    context = {
        "lottery": lottery,
        "participants": participants,
        "anomalies": anomalies,
        "winners": winners,
    }

    return render(request, "fortunaisk/lottery_detail.html", context)


@login_required
@permission_required("fortunaisk.terminate_lottery", raise_exception=True)
def terminate_lottery(request, lottery_id):
    lottery = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        try:
            # Logique pour terminer la loterie prématurément
            lottery.status = "cancelled"
            lottery.save(update_fields=["status"])
            messages.success(
                request, f"Lottery {lottery.lottery_reference} terminated successfully."
            )

            # Notifications si nécessaire
            send_alliance_auth_notification(
                user=request.user,
                title="Lottery Terminated",
                message=f"Lottery {lottery.lottery_reference} was terminated prematurely by {request.user.username}.",
                level="warning",
            )
            send_discord_notification(
                message=f"Lottery {lottery.lottery_reference} terminated prematurely by {request.user.username}."
            )
        except Exception as e:
            messages.error(request, "An error occurred while terminating the lottery.")
            logger.exception(f"Error terminating lottery {lottery_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/terminate_lottery_confirm.html", {"lottery": lottery}
    )


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_participants(request, lottery_id):
    lottery = get_object_or_404(Lottery, id=lottery_id)
    participants = lottery.ticket_purchases.select_related("user", "character").all()

    context = {
        "lottery": lottery,
        "participants": participants,
    }

    return render(request, "fortunaisk/lottery_participants.html", context)
