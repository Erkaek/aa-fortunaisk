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

logger = logging.getLogger(__name__)
User = get_user_model()


def get_distribution_range(winner_count):
    try:
        wc = int(winner_count)
        return range(max(wc, 1))
    except (ValueError, TypeError):
        return range(1)


##################################
#           ADMIN VIEWS
##################################


@login_required
@can_admin_app
def admin_dashboard(request):
    """
    Main admin dashboard:
    - Stats
    - Active & pending lotteries
    - Recent anomalies
    - Recent winners
    - Auto lotteries
    """
    # Overall counts
    total_lotteries = Lottery.objects.count()
    all_lotteries = Lottery.objects.exclude(status="cancelled")

    # Active & pending, with tickets_sold & participant_count
    active_qs = all_lotteries.filter(status__in=["active", "pending"])
    active_lotteries = active_qs.annotate(
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

    # Global stats
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

    processed_rows = TicketPurchase.objects.filter(status="processed").count()
    avg_participation = (
        (Decimal(processed_rows) / Decimal(total_lotteries)).quantize(Decimal("0.01"))
        if total_lotteries
        else Decimal("0.00")
    )

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

    # Top users by anomalies
    top_users = (
        TicketAnomaly.objects.values("user__username")
        .annotate(anomaly_count=Count("id"))
        .order_by("-anomaly_count")[:10]
    )
    top_users_names = [u["user__username"] for u in top_users]
    top_users_anomalies = [u["anomaly_count"] for u in top_users]
    top_active_users = zip(top_users_names, top_users_anomalies)

    # Automatic lotteries
    autolotteries = AutoLottery.objects.all()
    latest_anomalies = anomalies[:5]
    recent_winners = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")[:10]

    context = {
        "active_lotteries": active_lotteries,
        "anomalies": anomalies,
        "stats": stats,
        "anomaly_lottery_names": anomaly_lottery_names,
        "anomalies_per_lottery": anomalies_per_lottery,
        "top_active_users": top_active_users,
        "autolotteries": autolotteries,
        "latest_anomalies": latest_anomalies,
        "winners": recent_winners,
    }
    return render(request, "fortunaisk/admin.html", context)


@login_required
@can_admin_app
def resolve_anomaly(request, anomaly_id):
    anomaly = get_object_or_404(TicketAnomaly, id=anomaly_id)
    if request.method == "POST":
        anomaly.delete()
        messages.success(request, _("Anomaly resolved successfully."))
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@can_admin_app
def distribute_prize(request, winner_id):
    """
    Mark a Winner as 'distributed' — actual notification happens in your signal.
    """
    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        if not winner.distributed:
            winner.distributed = True
            winner.save(update_fields=["distributed"])
            messages.success(
                request,
                _("Marked prize as distributed for {username}.").format(
                    username=winner.ticket.user.username
                ),
            )
        else:
            messages.info(request, _("Prize was already distributed."))
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
            # initial lottery creation handled by signals/tasks
            messages.success(request, _("Auto-lottery created."))
            return redirect("fortunaisk:admin_dashboard")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm()
    dist_range = get_distribution_range(form.initial.get("winner_count", 1))
    if form.instance.winners_distribution:
        dist_range = range(len(form.instance.winners_distribution))
    return render(
        request,
        "fortunaisk/auto_lottery_form.html",
        {"form": form, "distribution_range": dist_range},
    )


@login_required
@can_admin_app
def edit_auto_lottery(request, autolottery_id):
    auto = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=auto)
        if form.is_valid():
            prev_active = auto.is_active
            auto = form.save()
            if auto.is_active and not prev_active:
                # scheduling handled in signals
                pass
            messages.success(request, _("Auto-lottery updated."))
            return redirect("fortunaisk:admin_dashboard")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm(instance=auto)
    dist_range = get_distribution_range(form.instance.winner_count or 1)
    if form.instance.winners_distribution:
        dist_range = range(len(form.instance.winners_distribution))
    return render(
        request,
        "fortunaisk/auto_lottery_form.html",
        {"form": form, "distribution_range": dist_range},
    )


@login_required
@can_admin_app
def delete_auto_lottery(request, autolottery_id):
    auto = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        auto.delete()
        messages.success(request, _("Auto-lottery deleted."))
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/auto_lottery_confirm_delete.html", {"autolottery": auto}
    )


##################################
#         USER VIEWS
##################################


@login_required
@can_access_app
def lottery(request):
    """
    Show active lotteries and allow users to see purchase instructions.
    """
    active_qs = Lottery.objects.filter(status="active").prefetch_related(
        "ticket_purchases"
    )
    counts = (
        TicketPurchase.objects.filter(user=request.user, lottery__in=active_qs)
        .values("lottery")
        .annotate(count=Sum("quantity"))
    )
    user_map = {c["lottery"]: c["count"] for c in counts}

    info = []
    for lot in active_qs:
        cnt = user_map.get(lot.id, 0)
        pct = (cnt / lot.max_tickets_per_user * 100) if lot.max_tickets_per_user else 0
        remaining = lot.max_tickets_per_user - cnt if lot.max_tickets_per_user else "∞"
        instructions = format_html(
            _(
                "Send <strong>{amount}</strong> ISK to <strong>{receiver}</strong> with ref <strong>{ref}</strong>"
            ),
            amount=lot.ticket_price,
            receiver=getattr(lot.payment_receiver, "corporation_name", "Unknown"),
            ref=lot.lottery_reference,
        )
        info.append(
            {
                "lottery": lot,
                "has_ticket": cnt > 0,
                "user_ticket_count": cnt,
                "max_tickets_per_user": lot.max_tickets_per_user,
                "remaining_tickets": remaining,
                "tickets_percentage": min(pct, 100),
                "instructions": instructions,
            }
        )

    return render(request, "fortunaisk/lottery.html", {"active_lotteries": info})


@login_required
@can_access_app
def winner_list(request):
    qs = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    # top 3 by total prize
    top3 = (
        User.objects.annotate(
            total_prize=Coalesce(
                Sum("ticket_purchases__winners__prize_amount"), Decimal("0")
            ),
            main_char=F("profile__main_character__character_name"),
        )
        .filter(total_prize__gt=0)
        .order_by("-total_prize")[:3]
    )
    return render(
        request, "fortunaisk/winner_list.html", {"page_obj": page, "top_3": top3}
    )


@login_required
@can_access_app
def lottery_history(request):
    per_page = int(request.GET.get("per_page", 6) or 6)
    past_qs = Lottery.objects.exclude(status="active").order_by("-end_date")
    paginator = Paginator(past_qs, per_page)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "fortunaisk/lottery_history.html",
        {
            "past_lotteries": page,
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
    lot = get_object_or_404(Lottery, id=lottery_id)
    qs = lot.ticket_purchases.select_related("user", "character")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "fortunaisk/lottery_participants.html",
        {"lottery": lot, "participants": page},
    )


@login_required
@can_admin_app
def terminate_lottery(request, lottery_id):
    lot = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        lot.status = "cancelled"
        lot.save(update_fields=["status"])
        messages.warning(
            request, _("Lottery {ref} cancelled.").format(ref=lot.lottery_reference)
        )
        return redirect("fortunaisk:admin_dashboard")
    return render(
        request, "fortunaisk/terminate_lottery_confirm.html", {"lottery": lot}
    )


@login_required
@can_admin_app
def anomalies_list(request):
    qs = TicketAnomaly.objects.select_related("lottery", "user", "character").order_by(
        "-recorded_at"
    )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(request, "fortunaisk/anomalies_list.html", {"page_obj": page})


@login_required
@can_admin_app
def lottery_detail(request, lottery_id):
    lot = get_object_or_404(Lottery, id=lottery_id)
    participants = Paginator(
        lot.ticket_purchases.select_related("user", "character"), 25
    ).get_page(request.GET.get("participants_page"))
    anomalies = Paginator(
        TicketAnomaly.objects.filter(lottery=lot).select_related("user", "character"),
        25,
    ).get_page(request.GET.get("anomalies_page"))
    winners = Paginator(
        Winner.objects.filter(ticket__lottery=lot).select_related(
            "ticket__user", "character"
        ),
        25,
    ).get_page(request.GET.get("winners_page"))

    participant_count = lot.ticket_purchases.values("user").distinct().count()
    tickets_sold = TicketPurchase.objects.filter(
        lottery=lot, status="processed"
    ).aggregate(total=Coalesce(Sum("quantity"), 0, output_field=IntegerField()))[
        "total"
    ]

    return render(
        request,
        "fortunaisk/lottery_detail.html",
        {
            "lottery": lot,
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
        {
            "ticket_purchases": tickets,
            "winnings": winnings,
        },
    )


@login_required
def export_winners_csv(request, lottery_id):
    lot = get_object_or_404(Lottery, id=lottery_id)
    winners = Winner.objects.filter(ticket__lottery=lot)
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = (
        f'attachment; filename="winners_{lot.lottery_reference}.csv"'
    )
    resp.write("Lottery Reference,User,Character,Prize Amount,Won At\n")
    for w in winners:
        resp.write(
            f"{w.ticket.lottery.lottery_reference},"
            f"{w.ticket.user.username},"
            f"{w.character or 'N/A'},"
            f"{w.prize_amount},"
            f"{w.won_at}\n"
        )
    return resp
