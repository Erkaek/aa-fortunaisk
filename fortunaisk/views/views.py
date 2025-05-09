# fortunaisk/views/views.py

# Standard Library
import logging
from decimal import Decimal

# Django
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, IntegerField, Q, Sum
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
    # All lotteries (excluding 'cancelled' for active listing)
    all_lotteries = Lottery.objects.exclude(status="cancelled")
    total_lotteries = Lottery.objects.count()

    # Active & pending lotteries with tickets_sold and participant_count
    active_lotteries = all_lotteries.filter(status__in=["active", "pending"]).annotate(
        tickets_sold=Coalesce(
            Sum(
                "ticket_purchases__quantity",
                filter=Q(ticket_purchases__status="processed"),
            ),
            0,
            output_field=IntegerField(),
        ),
        participant_count=Coalesce(
            Count(
                "ticket_purchases__user",
                filter=Q(ticket_purchases__status="processed"),
                distinct=True,
            ),
            0,
            output_field=IntegerField(),
        ),
    )

    # Global totals
    total_tickets_sold = TicketPurchase.objects.filter(status="processed").aggregate(
        total=Coalesce(Sum("quantity"), 0)
    )["total"]
    total_participants = (
        TicketPurchase.objects.filter(status="processed")
        .values("user")
        .distinct()
        .count()
    )
    total_prizes_distributed = Winner.objects.filter(distributed=True).aggregate(
        total=Coalesce(Sum("prize_amount"), Decimal("0"))
    )["total"]

    # Compute average participation: processed rows / total lotteries
    processed_rows = TicketPurchase.objects.filter(status="processed").count()
    if total_lotteries:
        avg_participation = (
            Decimal(processed_rows) / Decimal(total_lotteries)
        ).quantize(Decimal("0.01"))
    else:
        avg_participation = Decimal("0.00")

    # Anomalies and stats
    anomalies = TicketAnomaly.objects.select_related(
        "lottery", "user", "character"
    ).order_by("-recorded_at")

    stats = {
        "total_lotteries": total_lotteries,
        "total_tickets_sold": total_tickets_sold,
        "total_participants": total_participants,
        "total_anomalies": anomalies.count(),
        "avg_participation": avg_participation,
        "total_prizes_distributed": total_prizes_distributed,
    }

    # Anomalies per lottery (top 10)
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data]

    # Top users by anomalies (top 10)
    top_users = (
        TicketAnomaly.objects.values("user__username")
        .annotate(anomaly_count=Count("id"))
        .order_by("-anomaly_count")[:10]
    )
    top_users_names = [item["user__username"] for item in top_users]
    top_users_anomalies = [item["anomaly_count"] for item in top_users]
    top_active_users = zip(top_users_names, top_users_anomalies)

    # Automatic lotteries
    autolotteries = AutoLottery.objects.all()
    latest_anomalies = anomalies[:5]

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
        except Exception as e:
            messages.error(request, _("Error resolving anomaly."))
            logger.exception(e)
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@can_admin_app
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
            else:
                messages.info(request, _("This prize has already been distributed."))
        except Exception as e:
            messages.error(request, _("Error distributing prize."))
            logger.exception(e)
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/distribute_prize_confirm.html", {"winner": winner}
    )


##################################
#       AUTOLOTTERY VIEWS
##################################


@login_required
@can_admin_app
def create_auto_lottery(request):
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("AutoLottery created."))
            return redirect("fortunaisk:admin_dashboard")
        messages.error(request, _("Please correct the errors below."))
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
            prev_active = autolottery.is_active
            auto = form.save()
            if auto.is_active and not prev_active:
                create_lottery_from_auto_lottery.delay(auto.id)
            messages.success(request, _("AutoLottery updated."))
            return redirect("fortunaisk:admin_dashboard")
        messages.error(request, _("Please correct the errors below."))
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
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, _("AutoLottery deleted."))
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request,
        "fortunaisk/auto_lottery_confirm_delete.html",
        {"autolottery": autolottery},
    )


##################################
#         USER VIEWS
##################################


@login_required
@can_access_app
def lottery(request):
    active_lotteries = Lottery.objects.filter(status="active").prefetch_related(
        "ticket_purchases"
    )
    user_counts = (
        TicketPurchase.objects.filter(user=request.user, lottery__in=active_lotteries)
        .values("lottery")
        .annotate(count=Sum("quantity"))
    )
    user_map = {item["lottery"]: item["count"] for item in user_counts}

    lotteries_info = []
    for lot in active_lotteries:
        count = user_map.get(lot.id, 0)
        pct = (
            (count / lot.max_tickets_per_user * 100) if lot.max_tickets_per_user else 0
        )
        # Check if the user has already purchased tickets
        if lot.max_tickets_per_user:
            remaining = lot.max_tickets_per_user - count
            remaining = remaining if remaining > 0 else 0
        else:
            remaining = "∞"  # no limit
        lotteries_info.append(
            {
                "lottery": lot,
                "corporation_name": getattr(
                    lot.payment_receiver, "corporation_name", "Unknown"
                ),
                "has_ticket": count > 0,
                "instructions": format_html(
                    "Send <strong>{amount}</strong> ISK to <strong>{receiver}</strong> with <strong>{ref}</strong>",
                    amount=lot.ticket_price,
                    receiver=getattr(
                        lot.payment_receiver, "corporation_name", "Unknown"
                    ),
                    ref=lot.lottery_reference,
                ),
                "user_ticket_count": count,
                "max_tickets_per_user": lot.max_tickets_per_user,
                "remaining_tickets": remaining,
                "tickets_percentage": min(pct, 100),
            }
        )
    return render(
        request, "fortunaisk/lottery.html", {"active_lotteries": lotteries_info}
    )


@login_required
@can_access_app
def winner_list(request):
    winners_qs = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")
    top_3 = (
        User.objects.annotate(
            total_prize=Coalesce(
                Sum("ticket_purchases__winners__prize_amount"), Decimal("0")
            ),
            main_character_name=F("profile__main_character__character_name"),
        )
        .filter(total_prize__gt=0)
        .order_by("-total_prize")[:3]
        .select_related("profile__main_character")
    )
    paginator = Paginator(winners_qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request, "fortunaisk/winner_list.html", {"page_obj": page_obj, "top_3": top_3}
    )


@login_required
@can_access_app
def lottery_history(request):
    per_page = int(request.GET.get("per_page", 6) or 6)
    past_qs = Lottery.objects.exclude(status="active").order_by("-end_date")
    paginator = Paginator(past_qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "fortunaisk/lottery_history.html",
        {
            "past_lotteries": page_obj,
            "per_page": per_page,
            "per_page_choices": [6, 12, 24, 48],
        },
    )


@login_required
@can_admin_app
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Lottery created."))
            return redirect("fortunaisk:lottery")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = LotteryCreateForm()
    dist_range = get_distribution_range(form.instance.winner_count or 1)
    return render(
        request,
        "fortunaisk/standard_lottery_form.html",
        {"form": form, "distribution_range": dist_range},
    )


@login_required
@can_access_app
def lottery_participants(request, lottery_id):
    lottery = get_object_or_404(Lottery, id=lottery_id)
    qs = lottery.ticket_purchases.select_related("user", "character")
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "fortunaisk/lottery_participants.html",
        {"lottery": lottery, "participants": page_obj},
    )


@login_required
@can_admin_app
def terminate_lottery(request, lottery_id):
    lottery = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        lottery.status = "cancelled"
        lottery.save(update_fields=["status"])
        messages.success(
            request,
            _("Lottery {ref} terminated.").format(ref=lottery.lottery_reference),
        )
        send_alliance_auth_notification(
            user=request.user,
            title="Lottery Terminated",
            message=f"Lottery {lottery.lottery_reference} was terminated.",
            level="warning",
        )
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/terminate_lottery_confirm.html", {"lottery": lottery}
    )


@login_required
@can_admin_app
def anomalies_list(request):
    qs = TicketAnomaly.objects.select_related("lottery", "user", "character").order_by(
        "-recorded_at"
    )
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "fortunaisk/anomalies_list.html", {"page_obj": page_obj})


@login_required
@can_admin_app
def lottery_detail(request, lottery_id):
    # Récupère le lottery
    lottery = get_object_or_404(Lottery, id=lottery_id)

    # Pagine participants
    participants = Paginator(
        lottery.ticket_purchases.select_related("user", "character"), 25
    ).get_page(request.GET.get("participants_page"))

    # Pagine anomalies
    anomalies = Paginator(
        TicketAnomaly.objects.filter(lottery=lottery).select_related(
            "user", "character"
        ),
        25,
    ).get_page(request.GET.get("anomalies_page"))

    # Pagine winners
    winners = Paginator(
        Winner.objects.filter(ticket__lottery=lottery).select_related(
            "ticket__user", "character"
        ),
        25,
    ).get_page(request.GET.get("winners_page"))

    # Nombre de participants distincts
    participant_count = lottery.ticket_purchases.values("user").distinct().count()

    # Nombre de tickets vendus (status="processed")
    tickets_sold = TicketPurchase.objects.filter(
        lottery=lottery, status="processed"
    ).aggregate(total=Coalesce(Sum("quantity"), 0, output_field=IntegerField()))[
        "total"
    ]

    return render(
        request,
        "fortunaisk/lottery_detail.html",
        {
            "lottery": lottery,
            "participants": participants,
            "anomalies": anomalies,
            "winners": winners,
            "participant_count": participant_count,
            "tickets_sold": tickets_sold,
        },
    )


@login_required
@can_access_app
def user_dashboard(request):
    tickets = Paginator(
        TicketPurchase.objects.filter(user=request.user)
        .select_related("lottery", "character")
        .order_by("-purchase_date"),
        25,
    ).get_page(request.GET.get("tickets_page"))
    winnings = Paginator(
        Winner.objects.filter(ticket__user=request.user)
        .select_related("ticket__lottery", "character")
        .order_by("-won_at"),
        25,
    ).get_page(request.GET.get("winnings_page"))
    return render(
        request,
        "fortunaisk/user_dashboard.html",
        {"ticket_purchases": tickets, "winnings": winnings},
    )


@login_required
def export_winners_csv(request, lottery_id):
    lottery = get_object_or_404(Lottery, id=lottery_id)
    winners = Winner.objects.filter(ticket__lottery=lottery)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="winners_{lottery.lottery_reference}.csv"'
    )
    response.write("Lottery Reference,User,Character,Prize Amount,Won At\n")
    for w in winners:
        response.write(
            f"{w.ticket.lottery.lottery_reference},"
            f"{w.ticket.user.username},"
            f"{w.character or 'N/A'},"
            f"{w.prize_amount},"
            f"{w.won_at}\n"
        )
    return response
