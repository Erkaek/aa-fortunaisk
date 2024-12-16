from django.shortcuts import render
from django.contrib.auth.decorators import login_required, permission_required
from .models import Ticket, Winner

@login_required
def tickets_list(request):
    tickets = Ticket.objects.filter(character__character_ownership__user=request.user)
    return render(request, "fortunaisk/tickets_list.html", {"tickets": tickets})

@login_required
def winner_list(request):
    winners = Winner.objects.all()
    return render(request, "fortunaisk/winner_list.html", {"winners": winners})

@permission_required("fortunaisk.admin")
def admin_dashboard(request):
    return render(request, "fortunaisk/admin.html")
