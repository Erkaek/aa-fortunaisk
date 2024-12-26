# fortunaisk/views/admin_views.py

# Standard Library
import logging

# Django
from django.contrib import messages  # type: ignore
from django.contrib.auth.decorators import (  # type: ignore
    login_required,
    permission_required,
)
from django.db.models import Avg, Count, Sum  # type: ignore
from django.shortcuts import get_object_or_404, redirect, render  # type: ignore

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
    # Optimized queries with select_related and prefetch_related
    lotteries = (
        Lottery.objects.all()
        .select_related("payment_receiver")
        .prefetch_related("ticket_purchases")
    )
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

    # Anomalies per lottery
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data[:10]
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data[:10]]

    # Top Active Users
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
            messages.success(request, "Anomaly resolved successfully.")

            # Send notification via Alliance Auth
            send_alliance_auth_notification(
                user=request.user,
                title="Anomaly Resolved",
                message=f"Anomaly {anomaly_id} resolved for lottery {anomaly.lottery.lottery_reference}.",
                level="info",
            )

            # Send Discord notification
            send_discord_notification(
                message=f"Anomaly resolved: {anomaly.reason} for lottery {anomaly.lottery.lottery_reference} by {request.user.username}."
            )
        except Exception as e:
            messages.error(request, "An error occurred while resolving the anomaly.")
            logger.exception(f"Error resolving anomaly {anomaly_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@permission_required("fortunaisk.change_ticketanomaly", raise_exception=True)
def distribute_prize(request, winner_id):
    # fortunaisk
    from fortunaisk.notifications import (  # Local import
        send_alliance_auth_notification,
        send_discord_notification,
    )

    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        try:
            if not winner.distributed:
                winner.distributed = True
                winner.save()

                messages.success(
                    request, f"Prize distributed to {winner.ticket.user.username}."
                )

                # Send notification via Alliance Auth
                send_alliance_auth_notification(
                    user=request.user,
                    title="Prize Distributed",
                    message=f"Prizes of {winner.prize_amount} ISK distributed to {winner.ticket.user.username} for lottery {winner.ticket.lottery.lottery_reference}.",
                    level="success",
                )

                # Send Discord notification
                send_discord_notification(
                    message=f"Prize distributed: {winner.prize_amount} ISK to {winner.ticket.user.username} for lottery {winner.ticket.lottery.lottery_reference}."
                )
            else:
                messages.info(request, "This prize has already been distributed.")
        except Exception as e:
            messages.error(request, "An error occurred while distributing the prize.")
            logger.exception(f"Error distributing prize {winner_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/distribute_prize_confirm.html", {"winner": winner}
    )
