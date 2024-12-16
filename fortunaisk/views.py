# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .models import FortunaISKSettings, Ticket, Winner


@login_required
def lottery(request):
    settings = FortunaISKSettings.objects.first()
    has_ticket = Ticket.objects.filter(
        character__character_ownership__user=request.user
    ).exists()
    context = {"settings": settings, "has_ticket": has_ticket}
    return render(request, "lottery.html", context)


@login_required
def winner_list(request):
    winners = Winner.objects.all()
    return render(request, "winner_list.html", {"winners": winners})


@permission_required("fortunaisk.admin")
def admin_dashboard(request):
    return render(request, "admin.html")
