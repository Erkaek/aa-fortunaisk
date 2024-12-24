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
    lotteries = Lottery.objects.all().select_related()
    active_lotteries = lotteries.filter(status="active").annotate(
        tickets=Count("ticket_purchases")
    )
    ticket_purchases = (
        active_lotteries.aggregate(total=Sum("ticket_purchases__amount"))["total"] or 0
    )
    winners = Winner.objects.select_related("ticket__user", "ticket__lottery").order_by(
        "-won_at"
    )
    anomalies = TicketAnomaly.objects.select_related("lottery", "user").order_by(
        "-recorded_at"
    )

    stats = {
        "total_lotteries": lotteries.count(),
        "total_tickets": ticket_purchases,
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
        TicketAnomaly.objects.values("user__username")
        .annotate(anomaly_count=Count("id"))
        .order_by("-anomaly_count")[:10]
    )
    top_users_names = [item["user__username"] for item in top_users]
    top_users_anomalies = [item["anomaly_count"] for item in top_users]

    top_active_users = zip(top_users_names, top_users_anomalies)

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
    anomaly = get_object_or_404(TicketAnomaly, id=anomaly_id)
    if request.method == "POST":
        try:
            anomaly.delete()
            messages.success(request, "Anomalie résolue avec succès.")

            # Envoyer une notification via Alliance Auth
            send_alliance_auth_notification(
                user=request.user,
                title="Anomalie Résolue",
                message=f"Anomalie {anomaly_id} résolue pour la loterie {anomaly.lottery.lottery_reference}.",
                level="info",
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
@permission_required("fortunaisk.change_ticketanomaly", raise_exception=True)
def distribute_prize(request, winner_id):
    from fortunaisk.notifications import send_alliance_auth_notification, send_discord_notification  # Importation locale

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
                    user=request.user,
                    title="Gain Distribué",
                    message=f"Gains de {winner.prize_amount} ISK distribués à {winner.ticket.user.username} pour la loterie {winner.ticket.lottery.lottery_reference}.",
                    level="success",
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
    lottery = get_object_or_404(Lottery, id=lottery_id)
    participants = lottery.ticket_purchases.select_related("user").all()
    anomalies = TicketAnomaly.objects.filter(lottery=lottery).select_related("user")
    winners = Winner.objects.filter(ticket__lottery=lottery).select_related(
        "ticket__user"
    )

    context = {
        "lottery": lottery,
        "participants": participants,
        "anomalies": anomalies,
        "winners": winners,
    }

    return render(request, "fortunaisk/lottery_detail.html", context)
