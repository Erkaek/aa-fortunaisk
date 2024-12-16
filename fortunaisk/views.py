# Django
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from .models import FortunaISKSettings, Ticket, Winner


@login_required
def lottery(request):
    settings = FortunaISKSettings.objects.first()
    if settings is None:
        context = {
            "message": "No lottery is currently active. Please check back later.",
        }
        return render(request, "lottery.html", context)

    has_ticket = Ticket.objects.filter(
        character__character_ownership__user=request.user
    ).exists()

    context = {
        "settings": settings,
        "has_ticket": has_ticket,
        "instructions": f"Send {settings.ticket_price} ISK to {settings.payment_receiver} with reference '{settings.lottery_reference}' to participate.",
    }
    return render(request, "lottery.html", context)



@login_required
def winner_list(request):
    winners = Winner.objects.all()
    # Ajout du préfixe 'fortunaisk/' pour le chemin du template
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})


@permission_required("fortunaisk.admin")
def admin_dashboard(request):
    # Ajout du préfixe 'fortunaisk/' pour le chemin du template
    return render(request, "fortunaisk/admin.html")
