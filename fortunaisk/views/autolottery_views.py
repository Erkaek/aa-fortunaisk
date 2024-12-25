# fortunaisk/views/autolottery_views.py

# Standard Library
import logging

# Django
from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import (  # type: ignore
    login_required,
    permission_required,
)
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore

# fortunaisk
from fortunaisk.forms import AutoLotteryForm
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


@login_required
@permission_required("fortunaisk.view_autolottery", raise_exception=True)
def list_auto_lotteries(request):
    autolotteries = AutoLottery.objects.all()
    return render(
        request, "fortunaisk/auto_lottery_list.html", {"autolotteries": autolotteries}
    )


@login_required
@permission_required("fortunaisk.add_autolottery", raise_exception=True)
def create_auto_lottery(request):
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Loterie automatique créée avec succès.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AutoLotteryForm()

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
            "is_auto_lottery": True,
            "distribution_range": distribution_range,
        },
    )


@login_required
@permission_required("fortunaisk.change_autolottery", raise_exception=True)
def edit_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=autolottery)
        if form.is_valid():
            form.save()
            messages.success(request, "Loterie automatique mise à jour avec succès.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AutoLotteryForm(instance=autolottery)

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
            "is_auto_lottery": True,
            "distribution_range": distribution_range,
        },
    )


@login_required
@permission_required("fortunaisk.delete_autolottery", raise_exception=True)
def delete_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, "Loterie automatique supprimée avec succès.")
        return redirect("fortunaisk:auto_lottery_list")
    return render(
        request,
        "fortunaisk/auto_lottery_confirm_delete.html",
        {"autolottery": autolottery},
    )
