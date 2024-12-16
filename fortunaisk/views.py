# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import render

from .models import FortunaISKSettings, Ticket, Winner


@login_required
def lottery(request):
    settings = FortunaISKSettings.objects.first()
    has_ticket = Ticket.objects.filter(
        character__character_ownership__user=request.user
    ).exists()

    # Instructions à afficher uniquement si une loterie est en cours
    instructions = (
        f"Send {settings.ticket_price} ISK to {settings.payment_receiver} with reference '{settings.lottery_reference}' to participate."
        if settings
        else "No lottery is currently available."
    )

    context = {
        "settings": settings,
        "has_ticket": has_ticket,
        "instructions": instructions,
    }

    return render(request, "fortunaisk/lottery.html", context)


@login_required
def winner_list(request):
    winners = Winner.objects.all()
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})


@permission_required("fortunaisk.admin")
def admin_dashboard(request):
    return render(request, "fortunaisk/admin.html")
