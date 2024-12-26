# fortunaisk/views.py

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.forms import AutoLotteryForm, LotteryCreateForm
from fortunaisk.models import (
    AutoLottery,
    Lottery,
    TicketAnomaly,
    TicketPurchase,
    Winner,
)
from fortunaisk.notifications import (
    send_alliance_auth_notification,
    send_discord_notification,
)

logger = logging.getLogger(__name__)


##################################
#           ADMIN VIEWS
##################################

@login_required
@permission_required("fortunaisk.admin_dashboard", raise_exception=True)
def admin_dashboard(request):
    # Toutes les loteries
    lotteries = Lottery.objects.all().prefetch_related("ticket_purchases")

    # Loteries actives
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

    # Top Active Users (en fait, top anomalies par user)
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
        "top_users_names": top_users_names,
        "top_users_anomalies": top_users_anomalies,
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

            # Notifications
            send_alliance_auth_notification(
                user=request.user,
                title="Anomaly Resolved",
                message=f"Anomaly {anomaly_id} resolved for lottery {anomaly.lottery.lottery_reference}.",
                level="info",
            )
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
    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        try:
            if not winner.distributed:
                winner.distributed = True
                winner.save()

                messages.success(
                    request, f"Prize distributed to {winner.ticket.user.username}."
                )
                # Notifications
                send_alliance_auth_notification(
                    user=request.user,
                    title="Prize Distributed",
                    message=(
                        f"Prizes of {winner.prize_amount} ISK distributed to "
                        f"{winner.ticket.user.username} "
                        f"for lottery {winner.ticket.lottery.lottery_reference}."
                    ),
                    level="success",
                )
                send_discord_notification(
                    message=(
                        f"Prize distributed: {winner.prize_amount} ISK "
                        f"to {winner.ticket.user.username} "
                        f"for lottery {winner.ticket.lottery.lottery_reference}."
                    )
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


##################################
#       AUTOLOTTERY VIEWS
##################################

@login_required
@permission_required("fortunaisk.view_autolottery", raise_exception=True)
def list_auto_lotteries(request):
    autolotteries = AutoLottery.objects.all()
    return render(
        request, "fortunaisk/auto_lottery_list.html", {"autolotteries": autolotteries}
    )


@login_required
@permission_required("fortunaisk.add_autolottery", raise_exception=True)
def create_auto_lottery(request):
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Loterie automatique créée avec succès.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AutoLotteryForm()

    winner_count = form.instance.winner_count or 1
    try:
        winner_count = int(winner_count)
        if winner_count < 1:
            winner_count = 1
    except (ValueError, TypeError):
        winner_count = 1

    distribution_range = range(winner_count)

    return render(
        request,
        "fortunaisk/lottery_form.html",
        {
            "form": form,
            "is_auto_lottery": True,
            "distribution_range": distribution_range,
        },
    )


@login_required
@permission_required("fortunaisk.change_autolottery", raise_exception=True)
def edit_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=autolottery)
        if form.is_valid():
            form.save()
            messages.success(request, "Loterie automatique mise à jour avec succès.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AutoLotteryForm(instance=autolottery)

    winner_count = form.instance.winner_count or 1
    try:
        winner_count = int(winner_count)
        if winner_count < 1:
            winner_count = 1
    except (ValueError, TypeError):
        winner_count = 1

    distribution_range = range(winner_count)

    return render(
        request,
        "fortunaisk/lottery_form.html",
        {
            "form": form,
            "is_auto_lottery": True,
            "distribution_range": distribution_range,
        },
    )


@login_required
@permission_required("fortunaisk.delete_autolottery", raise_exception=True)
def delete_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, "Loterie automatique supprimée avec succès.")
        return redirect("fortunaisk:auto_lottery_list")
    return render(
        request,
        "fortunaisk/auto_lottery_confirm_delete.html",
        {"autolottery": autolottery},
    )


##################################
#         LOTTERY VIEWS
##################################

@login_required
def lottery(request):
    active_lotteries = (
        Lottery.objects.filter(status="active")
        .prefetch_related("ticket_purchases")
    )
    lotteries_info = []

    # Précharger les noms
    corp_ids = active_lotteries.values_list("payment_receiver", flat=True)
    corporations = EveCorporationInfo.objects.filter(corporation_id__in=corp_ids)
    corp_map = {corp.corporation_id: corp.corporation_name for corp in corporations}

    # Précompter les tickets pour l’utilisateur
    user_ticket_counts = (
        TicketPurchase.objects.filter(user=request.user, lottery__in=active_lotteries)
        .values("lottery")
        .annotate(count=Count("id"))
    )
    user_ticket_map = {item["lottery"]: item["count"] for item in user_ticket_counts}

    for lot in active_lotteries:
        corp_name = (
            lot.payment_receiver.corporation_name
            if lot.payment_receiver
            else "Unknown Corporation"
        )
        user_ticket_count = user_ticket_map.get(lot.id, 0)
        has_ticket = user_ticket_count > 0

        instructions = _(
            "To participate, send {ticket_price} ISK to {corp_name} with the reference '{lottery_reference}' in the payment description."
        ).format(
            ticket_price=lot.ticket_price,
            corp_name=corp_name,
            lottery_reference=lot.lottery_reference,
        )

        lotteries_info.append(
            {
                "lottery": lot,
                "corporation_name": corp_name,
                "has_ticket": has_ticket,
                "instructions": instructions,
                "user_ticket_count": user_ticket_count,
            }
        )

    return render(
        request,
        "fortunaisk/lottery.html",
        {"active_lotteries": lotteries_info},
    )


@login_required
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
def ticket_purchases(request):
    current_lotteries = Lottery.objects.filter(status="active")
    purchases = (
        TicketPurchase.objects.filter(lottery__in=current_lotteries)
        .select_related("user", "character", "lottery")
        .order_by("-purchase_date")
    )
    paginator = Paginator(purchases, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/ticket_purchases.html", {"page_obj": page_obj})


@login_required
@permission_required("fortunaisk.view_winner", raise_exception=True)
def winner_list(request):
    winners = Winner.objects.select_related(
        "character", "ticket__user", "ticket__lottery"
    ).order_by("-won_at")
    paginator = Paginator(winners, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/winner_list.html", {"page_obj": page_obj})


@login_required
def lottery_history(request):
    past_lotteries = (
        Lottery.objects.exclude(status="active")
        .prefetch_related("winners")
    )
    paginator = Paginator(past_lotteries, 6)  # 6 par page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "past_lotteries": page_obj,
        "page_obj": page_obj,
    }
    return render(request, "fortunaisk/lottery_history.html", context)


@login_required
@permission_required("fortunaisk.add_lottery", raise_exception=True)
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            lottery_obj = form.save(commit=False)
            lottery_obj.modified_by = request.user  # si vous souhaitez tracer l’utilisateur
            lottery_obj.save()
            messages.success(request, "Lottery created successfully.")
            return redirect("fortunaisk:lottery")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = LotteryCreateForm()

    winner_count = form.instance.winner_count or 1
    try:
        winner_count = int(winner_count)
        if winner_count < 1:
            winner_count = 1
    except (ValueError, TypeError):
        winner_count = 1

    distribution_range = range(winner_count)

    return render(
        request,
        "fortunaisk/lottery_form.html",
        {
            "form": form,
            "is_auto_lottery": False,
            "distribution_range": distribution_range,
        },
    )


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_detail(request, lottery_id):
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    participants = lottery_obj.ticket_purchases.select_related("user", "character").all()
    anomalies = TicketAnomaly.objects.filter(lottery=lottery_obj).select_related("user")
    winners = Winner.objects.filter(ticket__lottery=lottery_obj).select_related(
        "ticket__user", "character"
    )

    context = {
        "lottery": lottery_obj,
        "participants": participants,
        "anomalies": anomalies,
        "winners": winners,
    }
    return render(request, "fortunaisk/lottery_detail.html", context)


@login_required
@permission_required("fortunaisk.terminate_lottery", raise_exception=True)
def terminate_lottery(request, lottery_id):
    lottery_obj = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        try:
            lottery_obj.status = "cancelled"
            lottery_obj.save(update_fields=["status"])
            messages.success(
                request, f"Lottery {lottery_obj.lottery_reference} terminated successfully."
            )
            # Notifications
            send_alliance_auth_notification(
                user=request.user,
                title="Lottery Terminated",
                message=(
                    f"Lottery {lottery_obj.lottery_reference} was terminated prematurely "
                    f"by {request.user.username}."
                ),
                level="warning",
            )
            send_discord_notification(
                message=(
                    f"Lottery {lottery_obj.lottery_reference} terminated prematurely "
                    f"by {request.user.username}."
                )
            )
        except Exception as e:
            messages.error(request, "An error occurred while terminating the lottery.")
            logger.exception(f"Error terminating lottery {lottery_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/terminate_lottery_confirm.html", {"lottery": lottery_obj}
    )


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_participants(request, lottery_id):
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    participants = lottery_obj.ticket_purchases.select_related("user", "character").all()

    context = {
        "lottery": lottery_obj,
        "participants": participants,
    }
    return render(request, "fortunaisk/lottery_participants.html", context)


##################################
#          USER DASHBOARD
##################################

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
