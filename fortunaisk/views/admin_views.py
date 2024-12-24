# fortunaisk/views/admin_views.py

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render

# fortunaisk
from fortunaisk.models import Lottery, TicketAnomaly, TicketPurchase, Winner

logger = logging.getLogger(__name__)


@login_required
@permission_required("fortunaisk.admin_dashboard", raise_exception=True)
def admin_dashboard(request):
    """
    Tableau de bord admin personnalisé pour FortunaIsk.
    Affiche les statistiques globales, les loteries actives, les achats, les gagnants, les anomalies.
    """
    lotteries = Lottery.objects.all().select_related()
    active_lotteries = lotteries.filter(status="active").annotate(
        tickets=Count("ticket_purchases")
    )
    ticket_purchases = TicketPurchase.objects.select_related(
        "user", "character", "lottery"
    )
    winners = Winner.objects.select_related("character", "ticket__lottery")
    anomalies = TicketAnomaly.objects.select_related("lottery", "user", "character")

    stats = {
        "total_lotteries": lotteries.count(),
        "total_tickets": ticket_purchases.aggregate(total=Sum("amount"))["total"] or 0,
        "total_anomalies": anomalies.count(),
        "avg_participation": active_lotteries.aggregate(avg=Avg("tickets"))["avg"] or 0,
    }

    # Anomalies par loterie
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data[:10]
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data[:10]]

    # Top Utilisateurs Actifs
    top_users = (
        TicketPurchase.objects.values("user__username")
        .annotate(ticket_count=Count("id"))
        .order_by("-ticket_count")[:10]
    )
    # Récupérer deux listes distinctes
    top_users_names = [item["user__username"] for item in top_users]
    top_users_tickets = [item["ticket_count"] for item in top_users]

    # Zipper les deux listes en Python
    top_active_users = zip(top_users_names, top_users_tickets)

    context = {
        "lotteries": lotteries,
        "active_lotteries": active_lotteries,
        "ticket_purchases": ticket_purchases,
        "winners": winners,
        "anomalies": anomalies,
        "stats": stats,
        "lottery_names": list(
            active_lotteries.values_list("lottery_reference", flat=True)
        ),
        "tickets_per_lottery": list(active_lotteries.values_list("tickets", flat=True)),
        "anomaly_lottery_names": anomaly_lottery_names,
        "anomalies_per_lottery": anomalies_per_lottery,
        "top_active_users": top_active_users,
    }

    return render(request, "fortunaisk/admin.html", context)


@login_required
@permission_required("fortunaisk.terminate_lottery", raise_exception=True)
def terminate_lottery(request, lottery_id):
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    if lottery_obj.status == "active":
        lottery_obj.complete_lottery()
        messages.success(
            request,
            f"La loterie '{lottery_obj.lottery_reference}' a été terminée prématurément et les tâches de finalisation ont été lancées.",
        )
    else:
        messages.info(
            request,
            f"La loterie '{lottery_obj.lottery_reference}' n'est pas active et ne peut pas être terminée.",
        )
    return redirect("fortunaisk:admin_dashboard")
