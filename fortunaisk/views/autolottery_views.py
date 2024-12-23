# fortunaisk/views/autolottery_views.py

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

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
            messages.success(request, "Automatic lottery created successfully.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AutoLotteryForm()

    # Determine the distribution range based on the number of winners
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
            "is_auto_lottery": True,
            "distribution_range": distribution_range,  # Pass the variable
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
            messages.success(request, "Automatic lottery updated successfully.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = AutoLotteryForm(instance=autolottery)

    # Déterminer la plage de distribution basée sur le nombre de gagnants
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
        messages.success(request, "Automatic lottery deleted successfully.")
        return redirect("fortunaisk:auto_lottery_list")
    return render(
        request,
        "fortunaisk/auto_lottery_confirm_delete.html",
        {"autolottery": autolottery},
    )
