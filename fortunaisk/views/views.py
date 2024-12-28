# fortunaisk/views/views.py

# Standard Library
import logging

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Sum
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
from fortunaisk.notifications import (
    send_alliance_auth_notification,
    send_discord_notification,
)
from fortunaisk.tasks import (
    create_lottery_from_auto_lottery,  # Assurez-vous que cette fonction est utilisée
)

logger = logging.getLogger(__name__)


def get_distribution_range(winner_count):
    """
    Fonction utilitaire pour obtenir la plage de distribution en fonction du nombre de gagnants.
    """
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
@permission_required("fortunaisk.admin_dashboard", raise_exception=True)
def admin_dashboard(request):
    """
    Vue principale de l'admin, affichant des statistiques globales,
    la liste des loteries actives, les anomalies, etc.
    """
    # Toutes les loteries
    lotteries = Lottery.objects.all().prefetch_related("ticket_purchases")

    # Loteries actives
    active_lotteries = lotteries.filter(status="active").annotate(
        tickets=Count("ticket_purchases")
    )
    ticket_purchases_amount = (
        active_lotteries.aggregate(total=Sum("ticket_purchases__amount"))["total"] or 0
    )

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

    # Anomalies par loterie (top 10)
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data[:10]
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data[:10]]

    # Top Active Users (top anomalies par user) (top 10)
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
    """
    Vue pour résoudre une anomalie (TicketAnomaly).
    """
    anomaly = get_object_or_404(TicketAnomaly, id=anomaly_id)
    if request.method == "POST":
        try:
            anomaly.delete()
            messages.success(request, _("Anomalie résolue avec succès."))

            # Notifications
            send_alliance_auth_notification(
                user=request.user,
                title=_("Anomalie Résolue"),
                message=_(
                    "Anomalie {anomaly_id} résolue pour la loterie {lottery_ref}."
                ).format(
                    anomaly_id=anomaly.id,
                    lottery_ref=anomaly.lottery.lottery_reference,
                ),
                level="info",
            )
            send_discord_notification(
                message=_(
                    "Anomalie résolue : {reason} pour la loterie {lottery_ref} par {username}."
                ).format(
                    reason=anomaly.reason,
                    lottery_ref=anomaly.lottery.lottery_reference,
                    username=request.user.username,
                )
            )
        except Exception as e:
            messages.error(
                request,
                _("Une erreur est survenue lors de la résolution de l'anomalie."),
            )
            logger.exception(f"Error resolving anomaly {anomaly_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")

    return render(
        request, "fortunaisk/resolve_anomaly_confirm.html", {"anomaly": anomaly}
    )


@login_required
@permission_required("fortunaisk.change_winner", raise_exception=True)
def distribute_prize(request, winner_id):
    """
    Vue pour marquer le gain d'un winner comme 'distributed'.
    """
    winner = get_object_or_404(Winner, id=winner_id)
    if request.method == "POST":
        try:
            if not winner.distributed:
                winner.distributed = True
                winner.save()

                messages.success(
                    request,
                    _("Prix distribué à {username}.").format(
                        username=winner.ticket.user.username
                    ),
                )
                # Notifications
                send_alliance_auth_notification(
                    user=request.user,
                    title=_("Prix Distribué"),
                    message=_(
                        "Les prix de {prize_amount} ISK ont été distribués à {username} pour la loterie {lottery_ref}."
                    ).format(
                        prize_amount=winner.prize_amount,
                        username=winner.ticket.user.username,
                        lottery_ref=winner.ticket.lottery.lottery_reference,
                    ),
                    level="success",
                )
                send_discord_notification(
                    message=_(
                        "Prix distribué : {prize_amount} ISK à {username} pour la loterie {lottery_ref}."
                    ).format(
                        prize_amount=winner.prize_amount,
                        username=winner.ticket.user.username,
                        lottery_ref=winner.ticket.lottery.lottery_reference,
                    )
                )
            else:
                messages.info(request, _("Ce prix a déjà été distribué."))
        except Exception as e:
            messages.error(
                request, _("Une erreur est survenue lors de la distribution du prix.")
            )
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
    """
    Liste toutes les autolotteries actives.
    """
    # Liste toutes les AutoLotteries
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
            messages.success(request, "AutoLottery créée avec succès.")
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AutoLotteryForm()
    # Passer 'distribution_range' basé sur le nombre de gagnants initial
    distribution_range = range(form.initial.get("winner_count", 1))
    return render(
        request,
        "fortunaisk/autolottery_form.html",
        {"form": form, "distribution_range": distribution_range},
    )


@login_required
@permission_required("fortunaisk.change_autolottery", raise_exception=True)
def edit_auto_lottery(request, autolottery_id):
    """
    Vue pour éditer une AutoLottery existante.
    """
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=autolottery)
        if form.is_valid():
            previous_is_active = autolottery.is_active
            auto_lottery = form.save()
            if auto_lottery.is_active and not previous_is_active:
                # Si réactivé, créer une nouvelle loterie
                create_lottery_from_auto_lottery.delay(auto_lottery.id)
            messages.success(request, _("Loterie automatique mise à jour avec succès."))
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, _("Veuillez corriger les erreurs ci-dessous."))
    else:
        form = AutoLotteryForm(instance=autolottery)

    distribution_range = get_distribution_range(form.instance.winner_count or 1)

    context = {
        "form": form,
        "distribution_range": distribution_range,
    }
    return render(request, "fortunaisk/auto_lottery_form.html", context)


@login_required
@permission_required("fortunaisk.delete_autolottery", raise_exception=True)
def delete_auto_lottery(request, autolottery_id):
    """
    Vue pour supprimer une AutoLottery.
    """
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, _("Loterie automatique supprimée avec succès."))
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
    """
    Vue listant les loteries actives,
    donnant des instructions de participation à l'utilisateur.
    """
    active_lotteries = Lottery.objects.filter(status="active").prefetch_related(
        "ticket_purchases"
    )
    lotteries_info = []

    # Comptabiliser le nb de tickets de l'utilisateur
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
            else _("Unknown Corporation")
        )
        user_ticket_count = user_ticket_map.get(lot.id, 0)
        has_ticket = user_ticket_count > 0

        instructions = _(
            "Pour participer, envoyez {ticket_price} ISK à {corp_name} "
            "avec la référence '{lottery_reference}' dans la description du paiement."
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
    """
    Vue listant tous les achats de tickets
    pour les loteries actives (avec pagination).
    """
    current_lotteries = Lottery.objects.filter(status="active")
    purchases_qs = (
        TicketPurchase.objects.filter(lottery__in=current_lotteries)
        .select_related("user", "character", "lottery")
        .order_by("-purchase_date")
    )
    paginator = Paginator(purchases_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/ticket_purchases.html", {"page_obj": page_obj})


@login_required
@permission_required("fortunaisk.view_winner", raise_exception=True)
def winner_list(request):
    """
    Vue listant tous les winners (gagnants) avec pagination.
    """
    winners_qs = Winner.objects.select_related(
        "ticket__user", "ticket__lottery", "character"
    ).order_by("-won_at")
    paginator = Paginator(winners_qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/winner_list.html", {"page_obj": page_obj})


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_history(request):
    """
    Vue listant toutes les loteries passées (complétées ou annulées).
    """
    past_lotteries_qs = Lottery.objects.exclude(status="active").order_by("-end_date")
    paginator = Paginator(past_lotteries_qs, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "fortunaisk/lottery_history.html",
        {"past_lotteries": page_obj, "page_obj": page_obj},
    )


@login_required
@permission_required("fortunaisk.add_lottery", raise_exception=True)
def create_lottery(request):
    """
    Vue pour créer une loterie "unique" (non automatique).
    Gère LotteryCreateForm.
    """
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Loterie créée avec succès."))
            return redirect("fortunaisk:lottery")
        else:
            messages.error(request, _("Veuillez corriger les erreurs ci-dessous."))
            logger.error(f"Form errors in create_lottery: {form.errors}")
            # Utiliser winner_count soumis par l'utilisateur
            winner_count = form.data.get("winner_count", 1)
            distribution_range = get_distribution_range(winner_count)
    else:
        form = LotteryCreateForm()
        distribution_range = get_distribution_range(form.instance.winner_count or 1)

    context = {
        "form": form,
        "distribution_range": distribution_range,
    }
    return render(request, "fortunaisk/standard_lottery_form.html", context)


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_detail(request, lottery_id):
    """
    Vue d'un détail d'une loterie (participants, anomalies, winners, etc.)
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
@permission_required("fortunaisk.terminate_lottery", raise_exception=True)
def terminate_lottery(request, lottery_id):
    """
    Vue permettant de terminer prématurément une loterie active.
    """
    lottery_obj = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        try:
            lottery_obj.status = "cancelled"
            lottery_obj.save(update_fields=["status"])
            messages.success(
                request,
                _("Loterie {lottery_ref} terminée avec succès.").format(
                    lottery_ref=lottery_obj.lottery_reference
                ),
            )
            # Notifications
            send_alliance_auth_notification(
                user=request.user,
                title=_("Loterie Terminée"),
                message=_(
                    "La loterie {lottery_ref} a été terminée prématurément par {username}."
                ).format(
                    lottery_ref=lottery_obj.lottery_reference,
                    username=request.user.username,
                ),
                level="warning",
            )
            send_discord_notification(
                message=_(
                    "La loterie {lottery_ref} a été terminée prématurément par {username}."
                ).format(
                    lottery_ref=lottery_obj.lottery_reference,
                    username=request.user.username,
                )
            )
        except Exception as e:
            messages.error(
                request,
                _("Une erreur est survenue lors de la terminaison de la loterie."),
            )
            logger.exception(f"Error terminating lottery {lottery_id}: {e}")
        return redirect("fortunaisk:admin_dashboard")

    return render(
        request, "fortunaisk/terminate_lottery_confirm.html", {"lottery": lottery_obj}
    )


@login_required
@permission_required("fortunaisk.lottery_participants", raise_exception=True)
def lottery_participants(request, lottery_id):
    """
    Vue listant les participants d'une loterie.
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


##################################
#          USER DASHBOARD
##################################


@login_required
def user_dashboard(request):
    """
    Tableau de bord utilisateur : liste des tickets achetés et des gains.
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
