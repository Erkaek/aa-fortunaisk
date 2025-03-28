# fortunaisk/views/views.py

# Standard Library
import logging
from decimal import Decimal

# Django
from django.contrib import messages
from django.contrib.auth import (
    get_user_model,  # Assurez-vous que cette ligne est présente
)
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import format_html
from django.utils.translation import gettext as _

# fortunaisk
from fortunaisk.decorators import can_access_app, can_admin_app
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
@can_admin_app
def admin_dashboard(request):
    """
    Main admin dashboard: global stats, list of active lotteries,
    anomalies, winners, and automatic lotteries in one place.
    """
    # Exclude cancelled lotteries
    lotteries = Lottery.objects.exclude(status="cancelled").prefetch_related(
        "ticket_purchases"
    )

    # Add logs to verify filtering
    logger.debug(f"Total lotteries (excluding cancelled): {lotteries.count()}")
    sample_lotteries = lotteries.values_list("lottery_reference", flat=True)[:5]
    logger.debug(f"Sample lotteries: {list(sample_lotteries)}")

    # Active lotteries with annotations for tickets_sold and participant_count
    active_lotteries = lotteries.filter(status__in=["active", "pending"]).annotate(
        tickets_sold=Count(
            "ticket_purchases", filter=Q(ticket_purchases__status="processed")
        ),
        participant_count=Count("ticket_purchases__user", distinct=True),
    )

    # Financial summary calculations
    total_tickets_sold = TicketPurchase.objects.filter(status="processed").count()

    total_participants = (
        TicketPurchase.objects.filter(status="processed")
        .values("user")
        .distinct()
        .count()
    )

    # Total prizes distributed
    total_prizes_distributed = Winner.objects.filter(distributed=True).aggregate(
        total=Sum("prize_amount")
    )["total"] or Decimal("0")

    # Other statistics
    anomalies = TicketAnomaly.objects.select_related(
        "lottery", "user", "character"
    ).order_by("-recorded_at")

    stats = {
        "total_lotteries": lotteries.count(),
        "total_tickets_sold": total_tickets_sold,
        "total_participants": total_participants,
        "total_anomalies": anomalies.count(),
        "avg_participation": active_lotteries.aggregate(avg=Avg("participant_count"))[
            "avg"
        ]
        or 0,
        "total_prizes_distributed": total_prizes_distributed,
    }

    # Anomalies per lottery (top 10)
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data[:10]
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data[:10]]

    # Top active users by anomalies (top 10)
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

    # Latest Anomalies
    latest_anomalies = anomalies[:5]  # Display the latest 5 anomalies

    context = {
        "active_lotteries": active_lotteries,
        "winners": Winner.objects.select_related(
            "ticket__user", "ticket__lottery", "character"
        ).order_by("-won_at"),
        "anomalies": anomalies,
        "stats": stats,
        "anomaly_lottery_names": anomaly_lottery_names,
        "anomalies_per_lottery": anomalies_per_lottery,
        "top_users_names": top_users_names,
        "top_users_anomalies": top_users_anomalies,
        "top_active_users": top_active_users,
        "autolotteries": autolotteries,
        "latest_anomalies": latest_anomalies,
    }
    return render(request, "fortunaisk/admin.html", context)


@login_required
@can_admin_app
def resolve_anomaly(request, anomaly_id):
    """
    Allows an admin to resolve a specific ticket anomaly.
    """
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
@can_admin_app
def distribute_prize(request, winner_id):
    """
    Allows an admin to distribute a prize to a winner.
    """
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
@can_admin_app
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
@can_admin_app
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
@can_admin_app
def delete_auto_lottery(request, autolottery_id):
    """
    Allows an admin to delete an automatic lottery.
    """
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
@can_access_app
def lottery(request):
    """
    List of active lotteries for users and administrators.
    """
    active_lotteries = Lottery.objects.filter(status="active").prefetch_related(
        "ticket_purchases"
    )
    lotteries_info = []

    user_ticket_counts = (
        TicketPurchase.objects.filter(user=request.user, lottery__in=active_lotteries)
        .values("lottery")
        .annotate(count=Sum("quantity"))
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

        if lot.max_tickets_per_user and lot.max_tickets_per_user > 0:
            tickets_percentage = (user_ticket_count / lot.max_tickets_per_user) * 100
            tickets_percentage = min(tickets_percentage, 100)
        else:
            tickets_percentage = 0

        formatted_instructions = format_html(
            "To participate, send <strong>{amount}</strong> ISK to <strong>{receiver}</strong> with <strong>{lottery_id}</strong> as the payment description.",
            amount=lot.ticket_price,
            receiver=corp_name,
            lottery_id=lot.lottery_reference,
        )

        lotteries_info.append(
            {
                "lottery": lot,
                "corporation_name": corp_name,
                "has_ticket": has_ticket,
                "instructions": formatted_instructions,
                "user_ticket_count": user_ticket_count,
                "max_tickets_per_user": lot.max_tickets_per_user,
                "tickets_percentage": tickets_percentage,
            }
        )

    return render(
        request, "fortunaisk/lottery.html", {"active_lotteries": lotteries_info}
    )


@login_required
@can_access_app
def winner_list(request):
    """
    List of winners for users and administrators.
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
@can_access_app
def lottery_history(request):
    """
    Lottery history for users and administrators.
    """
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
@can_admin_app
def create_lottery(request):
    """
    Allows an admin to create a new lottery.
    """
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
            distribution_range = get_distribution_range(winner_count)

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
@can_access_app
def lottery_participants(request, lottery_id):
    """
    List of participants in a lottery, reserved for administrators.
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
@can_admin_app
def terminate_lottery(request, lottery_id):
    """
    Allows an admin to prematurely terminate an active lottery.
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
@can_admin_app
def anomalies_list(request):
    """
    Lists all anomalies for administrators.
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
@can_admin_app
def lottery_detail(request, lottery_id):
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

    # Calcul du nombre de participants uniques (distinct sur 'user')
    participant_count = participants_qs.values("user").distinct().count()

    context = {
        "lottery": lottery_obj,
        "participants": page_obj_participants,
        "anomalies": page_obj_anomalies,
        "winners": page_obj_winners,
        "participant_count": participant_count,
    }
    return render(request, "fortunaisk/lottery_detail.html", context)


##################################
#         USER VIEWS
##################################


@login_required
@can_access_app
def user_dashboard(request):
    """
    User dashboard for users and administrators.
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


@login_required
def export_winners_csv(request, lottery_id):
    lottery = Lottery.objects.get(id=lottery_id)
    winners = Winner.objects.filter(ticket__lottery=lottery)
    # Créez le CSV
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="winners_{lottery.lottery_reference}.csv"'
    )
    response.write("Lottery Reference,User,Character,Prize Amount,Won At\n")
    for winner in winners:
        response.write(
            f"{winner.ticket.lottery.lottery_reference},"
            f"{winner.ticket.user.username},"
            f"{winner.character if winner.character else 'N/A'},"
            f"{winner.prize_amount},"
            f"{winner.won_at}\n"
        )
    return response
