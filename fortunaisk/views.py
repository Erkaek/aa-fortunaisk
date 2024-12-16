# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .models import FortunaISKSettings, Ticket, Winner


@login_required
def lottery(request):
    # Récupérer les informations de la loterie actuelle
    settings = FortunaISKSettings.objects.first()
    tickets = Ticket.objects.filter(character__character_ownership__user=request.user)

    context = {
        "settings": settings,
        "has_ticket": tickets.exists(),
    }

    return render(request, "fortunaisk/lottery.html", context)


@login_required
def winner_list(request):
    winners = Winner.objects.all()
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})


@permission_required("fortunaisk.admin")
def admin_dashboard(request):
    return render(request, "fortunaisk/admin.html")
