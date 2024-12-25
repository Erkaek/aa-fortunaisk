# fortunaisk/views/user_views.py

# Standard Library
import logging

# Django
from django.contrib.auth.decorators import login_required  # type: ignore
from django.shortcuts import render  # type: ignore

# fortunaisk
from fortunaisk.models import TicketPurchase, Winner

logger = logging.getLogger(__name__)


@login_required
def user_dashboard(request):
    user = request.user
    ticket_purchases = (
        TicketPurchase.objects.filter(user=user)
        .select_related("lottery", "character")
        .order_by("-purchase_date")
    )
    winnings = (
        Winner.objects.filter(ticket__user=user)
        .select_related("ticket__lottery", "character")
        .order_by("-won_at")
    )

    return render(
        request,
        "fortunaisk/user_dashboard.html",
        {
            "ticket_purchases": ticket_purchases,
            "winnings": winnings,
        },
    )
