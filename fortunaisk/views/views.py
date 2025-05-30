# fortunaisk/views/views.py

# Standard Library
import logging
from decimal import Decimal

# Django
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Sum,
)
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
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
    WinnerDistribution,
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
    - Recent anomalies (unsolved)
    - Recent winners
    - Auto lotteries
    """
    # Overall counts
    total_lotteries = Lottery.objects.count()
    all_lotteries = Lottery.objects.exclude(status="cancelled")

    # Active & pending, with tickets_sold & participant_count
    active_lotteries = (
        all_lotteries.filter(status__in=["active", "pending"])
        .annotate(
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
        .annotate(
            gross_amount=ExpressionWrapper(
                F("ticket_price") * F("tickets_sold"),
                output_field=DecimalField(max_digits=25, decimal_places=2),
            )
        )
        .annotate(
            tax_collected=ExpressionWrapper(
                F("gross_amount") - F("total_pot"),
                output_field=DecimalField(max_digits=25, decimal_places=2),
            )
        )
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

    # Anomalies
    total_anomalies = TicketAnomaly.objects.count()
    unsolved_qs = TicketAnomaly.objects.filter(solved=False)
    resolved_qs = TicketAnomaly.objects.filter(solved=True)
    anomalies = unsolved_qs.select_related("lottery", "user", "character").order_by(
        "-recorded_at"
    )
    total_unsolved = unsolved_qs.count()
    total_resolved = resolved_qs.count()

    # Tax stats
    gross_amount = TicketPurchase.objects.aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00"))
    )["total"]
    net_amount = Lottery.objects.aggregate(
        total=Coalesce(Sum("total_pot"), Decimal("0.00"))
    )["total"]
    tax_collected = gross_amount - net_amount

    stats = {
        "total_lotteries": total_lotteries,
        "total_tickets_sold": total_tickets_sold,
        "total_participants": total_participants,
        "total_anomalies": total_anomalies,
        "total_unsolved_anomalies": total_unsolved,
        "total_resolved_anomalies": total_resolved,
        "avg_participation": avg_participation,
        "total_prizes_distributed": total_prizes_distributed,
        "tax_collected": tax_collected,
    }

    # Anomalies per lottery (unsolved top 10)
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
        TicketAnomaly.objects.filter(solved=False)
        .values("user__username")
        .annotate(anomaly_count=Count("id"))
        .order_by("-anomaly_count")[:10]
    )
    top_active_users = zip(
        [u["user__username"] for u in top_users],
        [u["anomaly_count"] for u in top_users],
    )

    # Automatic lotteries, recent anomalies & winners
    autolotteries = AutoLottery.objects.all()
    latest_anomalies = anomalies[:5]
    recent_winners = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")[:10]

    context = {
        "active_lotteries": active_lotteries,
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
    anomaly = get_object_or_404(TicketAnomaly, id=anomaly_id, solved=False)
    if request.method == "POST":
        detail = request.POST.get("detail", "")
        anomaly.solved = True
        anomaly.solved_at = timezone.now()
        anomaly.solved_by = request.user
        anomaly.detail = detail
        anomaly.save(update_fields=["solved", "solved_at", "solved_by", "detail"])
        messages.success(request, _("Anomaly marked as solved."))
        return redirect("fortunaisk:anomalies_list")
    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@can_admin_app
def resolved_anomalies_list(request):
    qs = (
        TicketAnomaly.objects.filter(solved=True)
        .select_related("lottery", "user", "character", "solved_by")
        .order_by("-solved_at")
    )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request, "fortunaisk/resolved_anomalies_list.html", {"page_obj": page}
    )


@login_required
@can_admin_app
def distribute_prize(request, winner_id):
    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        if not winner.distributed:
            winner.distributed = True
            winner.distributed_at = timezone.now()
            winner.distributed_by = request.user
            winner.save(
                update_fields=["distributed", "distributed_at", "distributed_by"]
            )
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
    """
    Create/edit an AutoLottery.
    """
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            auto = form.save()
            messages.success(
                request, _('Auto-lottery "%(name)s" created.') % {"name": auto.name}
            )
            return redirect("fortunaisk:admin_dashboard")
        else:
            for field, errs in form.errors.items():
                for e in errs:
                    if field == "__all__":
                        messages.error(request, e)
                    else:
                        label = form.fields[field].label or field
                        messages.error(request, f"{label} : {e}")
    else:
        form = AutoLotteryForm(
            initial={
                "winner_count": 1,
                "winners_distribution": [100],
            }
        )

    cnt = form.initial.get("winner_count", 1) or 1
    return render(
        request,
        "fortunaisk/auto_lottery_form.html",
        {
            "form": form,
            "distribution_range": range(max(int(cnt), 1)),
        },
    )


@login_required
@can_admin_app
def edit_auto_lottery(request, autolottery_id):
    auto = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=auto)
        if form.is_valid():
            form.save()
            messages.success(request, _("Auto-lottery updated."))
            return redirect("fortunaisk:admin_dashboard")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm(instance=auto)
    return render(
        request,
        "fortunaisk/auto_lottery_form.html",
        {
            "form": form,
            "distribution_range": range(max(auto.winner_count, 1)),
        },
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
                "corporation_name": getattr(
                    lot.payment_receiver, "corporation_name", "Unknown"
                ),
            }
        )

    return render(request, "fortunaisk/lottery.html", {"active_lotteries": info})


@login_required
@can_access_app
def winner_list(request):
    qs = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))

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

    # only truly "past" statuses
    allowed = ["completed", "cancelled", "pending"]

    # read the user's checked boxes
    selected = request.GET.getlist("status")
    if not selected:
        # default to both completed & cancelled
        selected = allowed.copy()
    # sanity-check
    selected = [s for s in selected if s in allowed]

    # filter & order
    qs = Lottery.objects.filter(status__in=selected).order_by("-end_date")

    page = Paginator(qs, per_page).get_page(request.GET.get("page"))

    return render(
        request,
        "fortunaisk/lottery_history.html",
        {
            "page_obj": page,
            "per_page": per_page,
            "per_page_choices": [6, 12, 24, 48],
            "allowed_statuses": allowed,
            "selected_statuses": selected,
        },
    )


@login_required
@can_admin_app
def create_lottery(request):
    """
    Create a standard lottery:
      1) create the Lottery,
      2) read the winners_distribution_entry inputs,
      3) create the WinnerDistribution,
      4) emit the signal.
    """
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            # 1) Create
            lottery = form.save()

            # 2) Read distribution
            raw_list = request.POST.getlist("winners_distribution_entry")
            try:
                dist_list = [Decimal(x) for x in raw_list]
            except Exception:
                messages.error(request, _("Invalid distribution."))
                lottery.delete()
                return redirect("fortunaisk:lottery_create")

            # 3) Validations
            if len(dist_list) != lottery.winner_count or sum(dist_list) != Decimal(
                "100"
            ):
                messages.error(
                    request,
                    _(
                        "The distribution must total 100% and match the number of winners."
                    ),
                )
                lottery.delete()
                return redirect("fortunaisk:lottery_create")

            # 4) Create entries
            for idx, pct in enumerate(dist_list, start=1):
                WinnerDistribution.objects.create(
                    lottery_reference=lottery.lottery_reference,
                    winner_rank=idx,
                    winner_prize_distribution=pct,
                )

            # 5) Emit signal for Discord notifications
            # fortunaisk
            from fortunaisk.signals.lottery_signals import lottery_created

            lottery_created.send(sender=Lottery, instance=lottery)

            messages.success(request, _("Lottery successfully created."))
            return redirect("fortunaisk:lottery")
        messages.error(request, _("Please correct the errors below."))
    else:
        form = LotteryCreateForm()

    dist_range = range(form.initial.get("winner_count", 1))
    return render(
        request,
        "fortunaisk/standard_lottery_form.html",
        {
            "form": form,
            "distribution_range": dist_range,
        },
    )


@login_required
@can_access_app
def lottery_participants(request, lottery_id):
    lot = get_object_or_404(Lottery, id=lottery_id)
    page = Paginator(
        lot.ticket_purchases.select_related("user", "character"), 25
    ).get_page(request.GET.get("page"))
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
    qs = (
        TicketAnomaly.objects.filter(solved=False)
        .select_related("lottery", "user", "character")
        .order_by("-recorded_at")
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
    distributions = WinnerDistribution.objects.filter(
        lottery_reference=lot.lottery_reference
    ).order_by("winner_rank")
    raw_amount = lot.ticket_price * tickets_sold
    tax_collected = (raw_amount - lot.total_pot).quantize(Decimal("0.01"))

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
            "distributions": distributions,
            "tax_collected": tax_collected,
        },
    )


@login_required
@can_access_app
def user_dashboard(request):
    tickets_page = Paginator(
        TicketPurchase.objects.filter(user=request.user)
        .select_related("lottery", "character")
        .order_by("-purchase_date"),
        9,
    ).get_page(request.GET.get("tickets_page"))

    winnings_page = Paginator(
        Winner.objects.filter(ticket__user=request.user)
        .select_related("ticket__lottery", "character")
        .order_by("-won_at"),
        9,
    ).get_page(request.GET.get("winnings_page"))

    # fortunaisk
    from fortunaisk.models.payment import ProcessedPayment

    payments_page = Paginator(
        ProcessedPayment.objects.filter(user=request.user)
        .select_related("character")
        .order_by("-payed_at"),
        10,
    ).get_page(request.GET.get("payments_page"))

    return render(
        request,
        "fortunaisk/user_dashboard.html",
        {
            "ticket_purchases": tickets_page,
            "winnings": winnings_page,
            "payments_page": payments_page,
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
    resp.write(
        "Lottery Reference,User,Character,Prize Amount,Won At,Distributed,Distributed At,Distributed By\n"
    )
    for w in winners:
        resp.write(
            f"{w.ticket.lottery.lottery_reference},"
            f"{w.ticket.user.username},"
            f"{getattr(w.character, 'character_name', 'N/A')},"
            f"{w.prize_amount},"
            f"{w.won_at.isoformat()},"
            f"{w.distributed},"
            f"{w.distributed_at.isoformat() if w.distributed_at else ''},"
            f"{getattr(w.distributed_by, 'username', '')}\n"
        )
    return resp


@login_required
@can_admin_app
def auto_lottery_toggle(request, autolottery_id):
    """
    Activate/deactivate an AutoLottery on the fly.
    """
    if request.method == "POST":
        auto = get_object_or_404(AutoLottery, id=autolottery_id)
        auto.is_active = not auto.is_active
        auto.save(update_fields=["is_active"])
        action = _("activated") if auto.is_active else _("paused")
        messages.success(
            request,
            _('Auto-lottery "%(name)s" %(action)s.')
            % {"name": auto.name, "action": action},
        )
    return redirect("fortunaisk:admin_dashboard")
