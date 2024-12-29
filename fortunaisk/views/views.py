# fortunaisk/views/views.py

# Standard Library
import logging
from decimal import Decimal

# Django
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

# fortunaisk
from fortunaisk.forms.autolottery_forms import AutoLotteryForm
from fortunaisk.forms.lottery_forms import LotteryCreateForm
from fortunaisk.models import (
    AutoLottery,
    Lottery,
    TicketAnomaly,
    TicketPurchase,
    Winner,
)
from fortunaisk.notifications import send_alliance_auth_notification
from fortunaisk.tasks import create_lottery_from_auto_lottery

logger = logging.getLogger(__name__)
User = get_user_model()


def get_distribution_range(winner_count):
    try:
        winner_count = int(winner_count)
        if winner_count < 1:
            winner_count = 1
    except (ValueError, TypeError):
        winner_count = 1
    return range(winner_count)


##################################
#           ADMIN VIEWS
##################################


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def admin_dashboard(request):
    """
    Main admin dashboard: global stats, list of active lotteries,
    anomalies, winners, and automatic lotteries in one place.
    """
    # All lotteries
    lotteries = Lottery.objects.all().prefetch_related("ticket_purchases")
    # Active lotteries
    active_lotteries = lotteries.filter(status="active").annotate(
        tickets=Count("ticket_purchases")
    )
    ticket_purchases_amount = active_lotteries.aggregate(
        total=Sum("ticket_purchases__amount")
    )["total"] or Decimal("0")

    winners = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")
    anomalies = TicketAnomaly.objects.select_related(
        "lottery", "user", "character"
    ).order_by("-recorded_at")

    stats = {
        "total_lotteries": lotteries.count(),
        "total_tickets": ticket_purchases_amount,
        "total_anomalies": anomalies.count(),
        "avg_participation": active_lotteries.aggregate(avg=Avg("tickets"))["avg"] or 0,
    }

    # Anomalies by lottery (top 10)
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data[:10]
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data[:10]]

    # Top Active Users (by anomalies) (top 10)
    top_users = (
        TicketAnomaly.objects.values("user__username")
        .annotate(anomaly_count=Count("id"))
        .order_by("-anomaly_count")[:10]
    )
    top_users_names = [item["user__username"] for item in top_users]
    top_users_anomalies = [item["anomaly_count"] for item in top_users]
    top_active_users = zip(top_users_names, top_users_anomalies)

    # Automatic Lotteries
    autolotteries = AutoLottery.objects.all()

    # Dernières Anomalies
    latest_anomalies = anomalies[:5]  # Afficher les 5 dernières anomalies

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
        "autolotteries": autolotteries,  # integrated from old auto_lottery_list
        "latest_anomalies": latest_anomalies,  # Ajout des dernières anomalies
    }
    return render(request, "fortunaisk/admin.html", context)


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def resolve_anomaly(request, anomaly_id):
    anomaly = get_object_or_404(TicketAnomaly, id=anomaly_id)
    if request.method == "POST":
        try:
            anomaly.delete()
            messages.success(request, _("Anomaly successfully resolved."))
            send_alliance_auth_notification(
                user=request.user,
                title="Anomaly Resolved",
                message=(
                    f"Anomaly {anomaly_id} resolved for lottery "
                    f"{anomaly.lottery.lottery_reference if anomaly.lottery else 'N/A'}."
                ),
                level="info",
            )
            # Discord notification is handled via signals if necessary
        except Exception as e:
            messages.error(request, _("An error occurred while resolving the anomaly."))
            logger.exception(f"Error resolving anomaly {anomaly_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")

    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def distribute_prize(request, winner_id):
    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        try:
            if not winner.distributed:
                winner.distributed = True
                winner.save()
                messages.success(
                    request,
                    _("Prize distributed to {username}.").format(
                        username=winner.ticket.user.username
                    ),
                )
                send_alliance_auth_notification(
                    user=request.user,
                    title="Prize Distributed",
                    message=(
                        f"{winner.prize_amount} ISK prize distributed to "
                        f"{winner.ticket.user.username} for lottery "
                        f"{winner.ticket.lottery.lottery_reference}."
                    ),
                    level="success",
                )
                # Discord notification is handled via signals if necessary
            else:
                messages.info(request, _("This prize has already been distributed."))
        except Exception as e:
            messages.error(
                request, _("An error occurred while distributing the prize.")
            )
            logger.exception(f"Error distributing prize {winner_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")

    return render(
        request, "fortunaisk/distribute_prize_confirm.html", {"winner": winner}
    )


##################################
#       AUTOLOTTERY VIEWS
#  Keep creation and editing, no separate listing page
##################################


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def create_auto_lottery(request):
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("AutoLottery successfully created."))
            return redirect("fortunaisk:admin_dashboard")
        else:
            messages.error(request, _("Please correct the errors below."))
            winner_count = form.data.get("winner_count", 1)
            distribution_range = get_distribution_range(winner_count)
    else:
        form = AutoLotteryForm()
        distribution_range = get_distribution_range(form.initial.get("winner_count", 1))

    if form.instance.winners_distribution:
        distribution_range = range(len(form.instance.winners_distribution))

    return render(
        request,
        "fortunaisk/auto_lottery_form.html",
        {"form": form, "distribution_range": distribution_range},
    )


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def edit_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=autolottery)
        if form.is_valid():
            previous_is_active = autolottery.is_active
            auto_lottery = form.save()
            if auto_lottery.is_active and not previous_is_active:
                create_lottery_from_auto_lottery.delay(auto_lottery.id)
            messages.success(request, _("AutoLottery updated successfully."))
            return redirect("fortunaisk:admin_dashboard")
        else:
            messages.error(request, _("Please correct the errors below."))
            winner_count = form.data.get("winner_count", 1)
            distribution_range = get_distribution_range(winner_count)
    else:
        form = AutoLotteryForm(instance=autolottery)
        distribution_range = get_distribution_range(form.instance.winner_count or 1)

    if form.instance.winners_distribution:
        distribution_range = range(len(form.instance.winners_distribution))

    return render(
        request,
        "fortunaisk/auto_lottery_form.html",
        {"form": form, "distribution_range": distribution_range},
    )


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def delete_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, _("AutoLottery successfully deleted."))
        return redirect("fortunaisk:admin_dashboard")

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
    """
    Lists active lotteries for regular users, with instructions to participate.
    """
    active_lotteries = Lottery.objects.filter(status="active").prefetch_related(
        "ticket_purchases"
    )
    lotteries_info = []

    user_ticket_counts = (
        TicketPurchase.objects.filter(user=request.user, lottery__in=active_lotteries)
        .values("lottery")
        .annotate(count=Count("id"))
    )
    user_ticket_map = {item["lottery"]: item["count"] for item in user_ticket_counts}

    for lot in active_lotteries:
        corp_name = (
            lot.payment_receiver.corporation_name
            if lot.payment_receiver and lot.payment_receiver.corporation_name
            else "Unknown Corporation"
        )
        user_ticket_count = user_ticket_map.get(lot.id, 0)
        has_ticket = user_ticket_count > 0

        instructions = f"To participate, send {lot.ticket_price} ISK to {corp_name} with '{lot.lottery_reference}' as the payment description."

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
@permission_required("fortunaisk.admin", raise_exception=True)
def winner_list(request):
    """
    Lists all winners with pagination, plus a podium of the best 3 by total amount.
    Shows the main character's name for each top winner.
    """
    # All winners, ordered by win date DESC
    winners_qs = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")

    # Top 3 users by total amount won with total_prize > 0
    top_3 = (
        User.objects.annotate(
            total_prize=Coalesce(
                Sum("ticket_purchases__winners__prize_amount"),
                Decimal("0"),
                output_field=DecimalField(),
            ),
            main_character_name=F("profile__main_character__character_name"),
        )
        .filter(total_prize__gt=0)
        .order_by("-total_prize")[:3]
        .select_related("profile__main_character")
    )

    # Pagination for the general table
    paginator = Paginator(winners_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "top_3": top_3,
    }
    return render(request, "fortunaisk/winner_list.html", context)


@login_required
def lottery_history(request):
    per_page = request.GET.get("per_page", 6)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 6

    past_lotteries_qs = Lottery.objects.exclude(status="active").order_by("-end_date")
    paginator = Paginator(past_lotteries_qs, per_page)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Define choices directly here
    per_page_choices = [6, 12, 24, 48]

    context = {
        "past_lotteries": page_obj,
        "page_obj": page_obj,
        "per_page": per_page,
        "per_page_choices": per_page_choices,
    }
    return render(request, "fortunaisk/lottery_history.html", context)


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Lottery successfully created."))
            return redirect("fortunaisk:lottery")
        else:
            # Form is invalid => re-build distribution_range from POST
            winner_count_str = request.POST.get("winner_count", "1")
            try:
                winner_count = int(winner_count_str)
            except ValueError:
                winner_count = 1
            distribution_range = range(winner_count)

            logger.debug(
                "[create_lottery] Form invalid. winner_count=%s => distribution_range=%s",
                winner_count,
                list(distribution_range),
            )

            return render(
                request,
                "fortunaisk/standard_lottery_form.html",
                {
                    "form": form,
                    "distribution_range": distribution_range,
                },
            )
    else:
        # GET => first load
        form = LotteryCreateForm()
        winner_count_initial = form.instance.winner_count or 1
        distribution_range = get_distribution_range(winner_count_initial)
        logger.debug(
            "[create_lottery] GET first load. winner_count_initial=%s => distribution_range=%s",
            winner_count_initial,
            list(distribution_range),
        )
        return render(
            request,
            "fortunaisk/standard_lottery_form.html",
            {
                "form": form,
                "distribution_range": distribution_range,
            },
        )


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def lottery_participants(request, lottery_id):
    """
    Lists participants of a lottery.
    """
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    participants_qs = lottery_obj.ticket_purchases.select_related(
        "user", "character"
    ).all()
    paginator = Paginator(participants_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "lottery": lottery_obj,
        "participants": page_obj,
    }
    return render(request, "fortunaisk/lottery_participants.html", context)


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def terminate_lottery(request, lottery_id):
    """
    Allows an admin to terminate an active lottery prematurely.
    """
    lottery_obj = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        try:
            lottery_obj.status = "cancelled"
            lottery_obj.save(update_fields=["status"])
            messages.success(
                request,
                _("Lottery {reference} terminated successfully.").format(
                    reference=lottery_obj.lottery_reference
                ),
            )
            send_alliance_auth_notification(
                user=request.user,
                title="Lottery Terminated",
                message=(
                    f"Lottery {lottery_obj.lottery_reference} was prematurely terminated "
                    f"by {request.user.username}."
                ),
                level="warning",
            )
            # Discord notification is handled via signals
        except Exception as e:
            messages.error(
                request, _("An error occurred while terminating the lottery.")
            )
            logger.exception(f"Error terminating lottery {lottery_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")

    return render(
        request, "fortunaisk/terminate_lottery_confirm.html", {"lottery": lottery_obj}
    )


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def anomalies_list(request):
    """
    Lists all anomalies, optionally with pagination.
    """
    anomalies_qs = TicketAnomaly.objects.select_related(
        "lottery", "user", "character"
    ).order_by("-recorded_at")

    # Pagination
    paginator = Paginator(anomalies_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
    }
    return render(request, "fortunaisk/anomalies_list.html", context)


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def lottery_detail(request, lottery_id):
    """
    Detailed view of a lottery (participants, anomalies, winners, etc.).
    """
    lottery_obj = get_object_or_404(Lottery, id=lottery_id)
    participants_qs = lottery_obj.ticket_purchases.select_related(
        "user", "character"
    ).all()
    paginator_participants = Paginator(participants_qs, 25)
    page_number_participants = request.GET.get("participants_page")
    page_obj_participants = paginator_participants.get_page(page_number_participants)

    anomalies_qs = TicketAnomaly.objects.filter(lottery=lottery_obj).select_related(
        "user", "character"
    )
    paginator_anomalies = Paginator(anomalies_qs, 25)
    page_number_anomalies = request.GET.get("anomalies_page")
    page_obj_anomalies = paginator_anomalies.get_page(page_number_anomalies)

    winners_qs = Winner.objects.filter(ticket__lottery=lottery_obj).select_related(
        "ticket__user", "character"
    )
    paginator_winners = Paginator(winners_qs, 25)
    page_number_winners = request.GET.get("winners_page")
    page_obj_winners = paginator_winners.get_page(page_number_winners)

    context = {
        "lottery": lottery_obj,
        "participants": page_obj_participants,
        "anomalies": page_obj_anomalies,
        "winners": page_obj_winners,
    }
    return render(request, "fortunaisk/lottery_detail.html", context)


@login_required
def user_dashboard(request):
    """
    User dashboard: lists the user's purchased tickets and any winnings.
    """
    user = request.user
    ticket_purchases_qs = (
        TicketPurchase.objects.filter(user=user)
        .select_related("lottery", "character")
        .order_by("-purchase_date")
    )
    paginator_tickets = Paginator(ticket_purchases_qs, 25)
    page_number_tickets = request.GET.get("tickets_page")
    page_obj_tickets = paginator_tickets.get_page(page_number_tickets)

    winnings_qs = (
        Winner.objects.filter(ticket__user=user)
        .select_related("ticket__lottery", "character")
        .order_by("-won_at")
    )
    paginator_winnings = Paginator(winnings_qs, 25)
    page_number_winnings = request.GET.get("winnings_page")
    page_obj_winnings = paginator_winnings.get_page(page_number_winnings)

    context = {
        "ticket_purchases": page_obj_tickets,
        "winnings": page_obj_winnings,
    }
    return render(request, "fortunaisk/user_dashboard.html", context)
