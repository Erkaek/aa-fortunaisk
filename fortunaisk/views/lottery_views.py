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
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore
from django.utils.translation import gettext as _  # type: ignore

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo  # type: ignore

# fortunaisk
from fortunaisk.forms import LotteryCreateForm
from fortunaisk.models import Lottery, TicketAnomaly, TicketPurchase, Winner

logger = logging.getLogger(__name__)


@login_required
def lottery(request):
    active_lotteries = Lottery.objects.filter(status="active").select_related()
    lotteries_info = []

    for lot in active_lotteries:
        corp_name = (
            EveCorporationInfo.objects.filter(corporation_id=lot.payment_receiver)
            .values_list("corporation_name", flat=True)
            .first()
            or "Corporation Inconnue"
        )

        user_ticket_count = TicketPurchase.objects.filter(
            user=request.user, lottery=lot
        ).count()
        has_ticket = user_ticket_count > 0

        instructions = _(
            "Pour participer, envoyez {ticket_price} ISK à {corp_name} avec la référence '{lottery_reference}' dans le motif de paiement."
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
    winners = Winner.objects.select_related("character", "ticket__lottery").order_by(
        "-won_at"
    )
    paginator = Paginator(winners, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/winner_list.html", {"page_obj": page_obj})


@login_required
def lottery_history(request):
    # Exemple: toutes les loteries complétées ou annulées
    past_lotteries = Lottery.objects.exclude(status="active").select_related()
    paginator = Paginator(past_lotteries, 6)  # 6 par page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "fortunaisk/lottery_history.html",
        {"past_lotteries": page_obj, "page_obj": page_obj},
    )


@login_required
@permission_required("fortunaisk.add_lottery", raise_exception=True)
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Loterie créée avec succès.")
            return redirect("fortunaisk:lottery")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
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
    participants = lottery.ticket_purchases.select_related("user").all()
    anomalies = TicketAnomaly.objects.filter(lottery=lottery).select_related("user")
    winners = Winner.objects.filter(ticket__lottery=lottery).select_related(
        "ticket__user"
    )

    context = {
        "lottery": lottery,
        "participants": participants,
        "anomalies": anomalies,
        "winners": winners,
    }

    return render(request, "fortunaisk/lottery_detail.html", context)
