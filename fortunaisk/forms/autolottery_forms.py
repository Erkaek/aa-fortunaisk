# fortunaisk/views/autolottery_views.py

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

# fortunaisk
from fortunaisk.forms import AutoLotteryForm

logger = logging.getLogger(__name__)


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
            "is_auto_lottery": True,
            "distribution_range": distribution_range,  # Passer la variable
        },
    )
