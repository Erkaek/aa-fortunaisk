# fortunaisk/views.py
"""Django views for the FortunaIsk lottery application."""

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

from .forms import AutoLotteryForm, LotteryCreateForm
from .models import AutoLottery, Lottery, TicketPurchase, Winner

logger = logging.getLogger(__name__)


@login_required
def lottery(request):
    active_lotteries = Lottery.objects.filter(status="active")
    lotteries_info = []

    for lot in active_lotteries:
        # Récupérer le nom de la corporation
        if str(lot.payment_receiver).isdigit():
            corp_name = (
                EveCorporationInfo.objects.filter(
                    corporation_id=int(lot.payment_receiver)
                )
                .values_list("corporation_name", flat=True)
                .first()
                or "Unknown Corporation"
            )
        else:
            corp_name = lot.payment_receiver

        # Vérifier si l'utilisateur a déjà un ticket
        user_ticket_count = TicketPurchase.objects.filter(
            user=request.user, lottery=lot
        ).count()
        has_ticket = user_ticket_count > 0

        # Instructions pour participer
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
        request, "fortunaisk/lottery.html", {"active_lotteries": lotteries_info}
    )


@login_required
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
def ticket_purchases(request):
    current_lotteries = Lottery.objects.filter(status="active")
    purchases = TicketPurchase.objects.filter(
        lottery__in=current_lotteries
    ).select_related("user", "character", "lottery")
    return render(request, "fortunaisk/ticket_purchases.html", {"purchases": purchases})


@permission_required("fortunaisk.admin", raise_exception=True)
def select_winner(request, lottery_id):
    messages.info(
        request,
        "Use the automated tasks to select winners. Manual selection not recommended now.",
    )
    return render(request, "fortunaisk/lottery.html", {})


@login_required
def winner_list(request):
    winners = Winner.objects.select_related("character", "ticket__lottery")
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def admin_dashboard(request):
    from .admin import admin_dashboard as admin_dash

    return admin_dash(request)


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
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    participants = TicketPurchase.objects.filter(lottery=lottery_obj).select_related(
        "user", "character"
    )
    return render(
        request,
        "fortunaisk/lottery_participants.html",
        {"lottery": lottery_obj, "participants": participants},
    )


@login_required
@permission_required("fortunaisk.add_lottery", raise_exception=True)
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Lottery created successfully."))
            return redirect("fortunaisk:lottery")
    else:
        form = LotteryCreateForm()

    return render(
        request,
        "fortunaisk/lottery_form.html",
        {"form": form, "is_auto_lottery": False},
    )


@login_required
@permission_required("fortunaisk.add_autolottery", raise_exception=True)
def create_auto_lottery(request):
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Automatic lottery created successfully."))
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm()
    return render(
        request, "fortunaisk/lottery_form.html", {"form": form, "is_auto_lottery": True}
    )


@login_required
@permission_required("fortunaisk.change_autolottery", raise_exception=True)
def edit_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=autolottery)
        if form.is_valid():
            form.save()
            messages.success(request, _("Automatic lottery updated successfully."))
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm(instance=autolottery)
    return render(
        request, "fortunaisk/lottery_form.html", {"form": form, "is_auto_lottery": True}
    )


@login_required
@permission_required("fortunaisk.delete_autolottery", raise_exception=True)
def delete_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, _("Automatic lottery deleted successfully."))
        return redirect("fortunaisk:auto_lottery_list")
    return render(
        request,
        "fortunaisk/auto_lottery_confirm_delete.html",
        {"autolottery": autolottery},
    )


@login_required
@permission_required("fortunaisk.view_autolottery", raise_exception=True)
def list_auto_lotteries(request):
    autolotteries = AutoLottery.objects.all()
    return render(
        request, "fortunaisk/auto_lottery_list.html", {"autolotteries": autolotteries}
    )
