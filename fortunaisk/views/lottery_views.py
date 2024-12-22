# fortunaisk/views/lottery_views.py

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.forms import LotteryCreateForm
from fortunaisk.models import Lottery, TicketPurchase, Winner

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
            or "Unknown Corporation"
        )

        user_ticket_count = TicketPurchase.objects.filter(
            user=request.user, lottery=lot
        ).count()
        has_ticket = user_ticket_count > 0

        instructions = _(
            "To participate, send {ticket_price} ISK to {corp_name} with the reference '{lottery_reference}' in the payment reason."
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
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
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
    # example: all completed or cancelled lotteries
    past_lotteries = Lottery.objects.exclude(status="active").select_related()
    paginator = Paginator(past_lotteries, 6)  # 6 per page
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
            messages.success(request, "Lottery created successfully.")
            return redirect("fortunaisk:lottery")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LotteryCreateForm()

    # Déterminer le nombre de gagnants pour distribution_range
    if request.method == "POST":
        winner_count = request.POST.get("winner_count", 1)
    else:
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
            "distribution_range": distribution_range,  # Passer la variable
        },
    )


@login_required
@permission_required("fortunaisk.terminate_lottery", raise_exception=True)
def terminate_lottery(request, lottery_id):
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    if lottery_obj.status == "active":
        lottery_obj.status = "completed"
        lottery_obj.save()
        messages.success(
            request,
            f"Lottery '{lottery_obj.lottery_reference}' has been terminated prematurely.",
        )
    return redirect("fortunaisk:admin_dashboard")


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_participants(request, lottery_id):
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    participants = (
        TicketPurchase.objects.filter(lottery=lottery_obj)
        .select_related("user", "character")
        .order_by("-purchase_date")
    )

    return render(
        request,
        "fortunaisk/lottery_participants.html",
        {"lottery": lottery_obj, "participants": participants},
    )
