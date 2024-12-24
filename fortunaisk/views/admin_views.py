# fortunaisk/views/admin_views.py

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render

# fortunaisk
from fortunaisk.models import Lottery, TicketAnomaly, Winner
from fortunaisk.notifications import (
    send_alliance_auth_notification,
    send_discord_notification,
)

logger = logging.getLogger(__name__)


@login_required
@permission_required("fortunaisk.admin_dashboard", raise_exception=True)
def admin_dashboard(request):
    """
    Tableau de bord admin personnalisé pour FortunaIsk.
    Affiche les statistiques globales, les loteries actives, les achats, les gagnants, les anomalies.
    """
    lotteries = Lottery.objects.all()
    active_lotteries = lotteries.filter(status="active").annotate(
        tickets=Count("ticket_purchase")
    )
    winners = Winner.objects.select_related("ticket__lottery", "character").order_by(
        "-won_at"
    )
    anomalies = TicketAnomaly.objects.select_related(
        "lottery", "user", "character"
    ).order_by("-recorded_at")

    stats = {
        "total_lotteries": lotteries.count(),
        "total_tickets": lotteries.aggregate(total=Sum("ticket_purchase__amount"))[
            "total"
        ]
        or 0,
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
        Lottery.objects.values("ticket_purchase__user__username")
        .annotate(ticket_count=Count("ticket_purchase"))
        .order_by("-ticket_count")[:10]
    )
    top_users_names = [item["ticket_purchase__user__username"] for item in top_users]
    top_users_tickets = [item["ticket_count"] for item in top_users]
    top_active_users = zip(top_users_names, top_users_tickets)

    context = {
        "active_lotteries": active_lotteries,
        "winners": winners,
        "anomalies": anomalies,
        "stats": stats,
        "anomaly_lottery_names": anomaly_lottery_names,
        "anomalies_per_lottery": anomalies_per_lottery,
        "top_active_users": top_active_users,
    }

    return render(request, "fortunaisk/admin.html", context)


@login_required
@permission_required("fortunaisk.change_ticketanomaly", raise_exception=True)
def resolve_anomaly(request, anomaly_id):
    """
    Vue pour résoudre une anomalie spécifique.
    """
    anomaly = get_object_or_404(TicketAnomaly, id=anomaly_id)
    if request.method == "POST":
        try:
            anomaly.delete()
            messages.success(request, "Anomalie résolue avec succès.")

            # Envoyer une notification via Alliance Auth
            send_alliance_auth_notification(
                event_type="anomaly_resolved",
                user=request.user,
                context={
                    "anomaly_id": anomaly_id,
                    "lottery_reference": anomaly.lottery.lottery_reference,
                },
            )

            # Envoyer une notification Discord
            send_discord_notification(
                message=f"Anomalie résolue : {anomaly.reason} pour la loterie {anomaly.lottery.lottery_reference} par {request.user.username}."
            )
        except Exception as e:
            messages.error(
                request, "Une erreur est survenue lors de la résolution de l'anomalie."
            )
            logger.exception(
                f"Erreur lors de la résolution de l'anomalie {anomaly_id}: {e}"
            )
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@permission_required("fortunaisk.change_winner", raise_exception=True)
def distribute_prize(request, winner_id):
    """
    Vue pour marquer un gain comme distribué.
    """
    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        try:
            if not winner.distributed:
                winner.distributed = True
                winner.save()

                messages.success(
                    request, f"Gain distribué à {winner.ticket.user.username}."
                )

                # Envoyer une notification via Alliance Auth
                send_alliance_auth_notification(
                    event_type="prize_distributed",
                    user=request.user,
                    context={
                        "winner_id": winner_id,
                        "user": winner.ticket.user.username,
                        "prize_amount": winner.prize_amount,
                    },
                )

                # Envoyer une notification Discord
                send_discord_notification(
                    message=f"Gain distribué : {winner.prize_amount} ISK à {winner.ticket.user.username} pour la loterie {winner.ticket.lottery.lottery_reference}."
                )
            else:
                messages.info(request, "Ce gain a déjà été distribué.")
        except Exception as e:
            messages.error(
                request, "Une erreur est survenue lors de la distribution du gain."
            )
            logger.exception(f"Erreur lors de la distribution du gain {winner_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/distribute_prize_confirm.html", {"winner": winner}
    )


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_detail(request, lottery_id):
    """
    Vue détaillée pour une loterie spécifique.
    Affiche les participants, anomalies et gagnants.
    """
    lottery = get_object_or_404(Lottery, id=lottery_id)
    participants = lottery.ticket_purchase.select_related("user", "character").all()
    anomalies = TicketAnomaly.objects.filter(lottery=lottery).select_related(
        "user", "character"
    )
    winners = Winner.objects.filter(ticket__lottery=lottery).select_related(
        "ticket__user", "character"
    )

    context = {
        "lottery": lottery,
        "participants": participants,
        "anomalies": anomalies,
        "winners": winners,
    }

    return render(request, "fortunaisk/lottery_detail.html", context)
