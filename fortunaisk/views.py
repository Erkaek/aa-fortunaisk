# fortunaisk/views.py
"""Vues Django pour l'application de loterie FortunaIsk."""

# Standard Library
import logging
import random

# Django
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.signals import post_save  # Ajouté
from django.dispatch import receiver  # Ajouté
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

from .forms import AutoLotteryForm, LotteryCreateForm
from .models import (
    AutoLottery,
    Lottery,
    TicketAnomaly,
    TicketPurchase,
    UserProfile,
    Winner,
)
from .notifications import send_discord_notification  # Import depuis notifications.py

logger = logging.getLogger(__name__)


@login_required
def lottery(request):
    active_lotteries = Lottery.objects.filter(status="active")
    lotteries_info = []

    for lot in active_lotteries:
        # Récupérer le nom de la corporation
        if str(lot.payment_receiver).isdigit():
            corp_name = (
                EveCorporationInfo.objects.filter(
                    corporation_id=int(lot.payment_receiver)
                )
                .values_list("corporation_name", flat=True)
                .first()
                or "Unknown Corporation"
            )
        else:
            corp_name = lot.payment_receiver

        # Vérifier si l'utilisateur a déjà un ticket
        user_ticket_count = TicketPurchase.objects.filter(
            user=request.user, lottery=lot
        ).count()
        has_ticket = user_ticket_count > 0

        # Instructions pour participer
        instructions = _(
            "To participate, send {ticket_price} ISK to {corp_name} with the reference '{lottery_reference}' in the payment reason."
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
        request, "fortunaisk/lottery.html", {"active_lotteries": lotteries_info}
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

    # Pagination
    paginator = Paginator(purchases, 25)  # 25 achats par page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/ticket_purchases.html", {"page_obj": page_obj})


@permission_required("fortunaisk.admin", raise_exception=True)
def select_winner(request, lottery_id):
    messages.info(
        request,
        "Use the automated tasks to select winners. Manual selection not recommended now.",
    )
    return redirect("fortunaisk:admin_dashboard")


@login_required
@permission_required("fortunaisk.view_ticketpurchase", raise_exception=True)
def winner_list(request):
    winners = Winner.objects.select_related("character", "ticket__lottery").order_by(
        "-won_at"
    )

    # Pagination
    paginator = Paginator(winners, 25)  # 25 gagnants par page
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "fortunaisk/winner_list.html", {"page_obj": page_obj})


@login_required
@permission_required("fortunaisk.admin_dashboard", raise_exception=True)
def admin_dashboard(request):
    """
    Vue personnalisée pour le tableau de bord administrateur de FortunaIsk.
    """
    lotteries = Lottery.objects.all()
    active_lotteries = lotteries.filter(status="active")
    ticket_purchases = TicketPurchase.objects.all()
    winners = Winner.objects.all()
    anomalies = TicketAnomaly.objects.all()

    # Statistiques
    stats = {
        "total_lotteries": lotteries.count(),
        "total_tickets": ticket_purchases.aggregate(total=Sum("amount"))["total"] or 0,
        "total_anomalies": anomalies.count(),
        "avg_participation": lotteries.filter(status="active").aggregate(
            avg=Count("participant_count")
        )["avg"]
        or 0,
    }

    # Graphiques supplémentaires
    # Anomalies par Loterie
    anomaly_data = (
        anomalies.values("lottery__lottery_reference")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_lottery_names = [
        item["lottery__lottery_reference"] for item in anomaly_data
    ]
    anomalies_per_lottery = [item["count"] for item in anomaly_data]

    # Top Active Users
    top_users = (
        TicketPurchase.objects.values("user__username")
        .annotate(ticket_count=Count("id"))
        .order_by("-ticket_count")[:10]
    )
    top_users_names = [item["user__username"] for item in top_users]
    top_users_tickets = [item["ticket_count"] for item in top_users]

    # Limiter les labels pour éviter trop de segments dans les graphiques
    if len(anomaly_lottery_names) > 10:
        anomaly_lottery_names = anomaly_lottery_names[:10]
        anomalies_per_lottery = anomalies_per_lottery[:10]

    context = {
        "lotteries": lotteries,
        "active_lotteries": active_lotteries,  # Ajout de cette ligne
        "ticket_purchases": ticket_purchases,
        "winners": winners,
        "anomalies": anomalies,
        "stats": stats,
        "lottery_names": list(
            active_lotteries.values_list("lottery_reference", flat=True)
        ),  # Utilisation des loteries actives
        "tickets_per_lottery": list(
            active_lotteries.annotate(tickets=Count("ticketpurchase")).values_list(
                "tickets", flat=True
            )
        ),
        "total_pots": list(active_lotteries.values_list("total_pot", flat=True)),
        "anomaly_lottery_names": anomaly_lottery_names,
        "anomalies_per_lottery": anomalies_per_lottery,
        "top_users_names": top_users_names,
        "top_users_tickets": top_users_tickets,
    }

    return render(request, "fortunaisk/admin.html", context)


@login_required
def user_dashboard(request):
    user = request.user
    ticket_purchases = TicketPurchase.objects.filter(user=user).select_related(
        "lottery", "character"
    )
    winnings = Winner.objects.filter(ticket__user=user).select_related(
        "ticket__lottery", "character"
    )
    return render(
        request,
        "fortunaisk/user_dashboard.html",
        {"ticket_purchases": ticket_purchases, "winnings": winnings},
    )


@login_required
@permission_required("fortunaisk.add_lottery", raise_exception=True)
def create_lottery(request):
    if request.method == "POST":
        form = LotteryCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Lottery created successfully."))
            return redirect("fortunaisk:lottery")
    else:
        form = LotteryCreateForm()

    return render(
        request,
        "fortunaisk/lottery_form.html",
        {"form": form, "is_auto_lottery": False},
    )


@login_required
@permission_required("fortunaisk.add_autolottery", raise_exception=True)
def create_auto_lottery(request):
    if request.method == "POST":
        form = AutoLotteryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Automatic lottery created successfully."))
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm()
    return render(
        request, "fortunaisk/lottery_form.html", {"form": form, "is_auto_lottery": True}
    )


@login_required
@permission_required("fortunaisk.change_autolottery", raise_exception=True)
def edit_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        form = AutoLotteryForm(request.POST, instance=autolottery)
        if form.is_valid():
            form.save()
            messages.success(request, _("Automatic lottery updated successfully."))
            return redirect("fortunaisk:auto_lottery_list")
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = AutoLotteryForm(instance=autolottery)
    return render(
        request, "fortunaisk/lottery_form.html", {"form": form, "is_auto_lottery": True}
    )


@login_required
@permission_required("fortunaisk.delete_autolottery", raise_exception=True)
def delete_auto_lottery(request, autolottery_id):
    autolottery = get_object_or_404(AutoLottery, id=autolottery_id)
    if request.method == "POST":
        autolottery.delete()
        messages.success(request, _("Automatic lottery deleted successfully."))
        return redirect("fortunaisk:auto_lottery_list")
    return render(
        request,
        "fortunaisk/auto_lottery_confirm_delete.html",
        {"autolottery": autolottery},
    )


@login_required
@permission_required("fortunaisk.view_autolottery", raise_exception=True)
def list_auto_lotteries(request):
    autolotteries = AutoLottery.objects.all()
    return render(
        request, "fortunaisk/auto_lottery_list.html", {"autolotteries": autolotteries}
    )


@login_required
def create_ticket_purchase(request, lottery_id):
    """
    Vue pour gérer la création d'un ticket d'achat par un utilisateur.
    """
    lottery = get_object_or_404(Lottery, id=lottery_id, status="active")
    if request.method == "POST":
        # Logique de création de ticket ici
        # Par exemple, création du ticket d'achat
        try:
            with transaction.atomic():
                ticket = TicketPurchase.objects.create(
                    user=request.user,
                    character=request.user.evecharacter,  # Assurez-vous que l'utilisateur a un personnage associé
                    lottery=lottery,
                    amount=lottery.ticket_price,
                    payment_id=random.randint(
                        100000, 999999
                    ),  # Exemple de génération d'ID
                )
                # Utilisation de la variable 'ticket' pour éviter l'erreur F841
                logger.debug(f"Ticket créé avec l'ID: {ticket.id}")

                # Mise à jour des statistiques de la loterie
                lottery.participant_count += 1
                lottery.total_pot += int(lottery.ticket_price)
                lottery.save()

                # Ajouter des points
                profile, _ = UserProfile.objects.get_or_create(user=request.user)
                profile.points += 10  # Par exemple, 10 points par ticket acheté
                profile.save()

                messages.success(
                    request, _("Ticket acheté avec succès. Vous avez gagné 10 points!")
                )
                return redirect("fortunaisk:lottery")
        except Exception as e:
            logger.error(f"Erreur lors de l'achat de ticket: {e}")
            messages.error(
                request, _("Erreur lors de l'achat du ticket. Veuillez réessayer.")
            )
            return redirect("fortunaisk:lottery")
    else:
        # Afficher le formulaire ou les instructions
        instructions = _(
            "Pour acheter un ticket, veuillez effectuer le paiement via votre méthode préférée."
        )
        return render(
            request,
            "fortunaisk/create_ticket_purchase.html",
            {"lottery": lottery, "instructions": instructions},
        )


@receiver(post_save, sender=Winner)
def award_points_to_winners(sender, instance, created, **kwargs):
    if created:
        profile, created = UserProfile.objects.get_or_create(user=instance.ticket.user)
        profile.points += 100  # Par exemple, 100 points par gain
        profile.save()
        profile.check_rewards()
        send_discord_notification(
            message=f"Félicitations {instance.ticket.user.username}, vous avez gagné 100 points!"
        )


@login_required
@permission_required("fortunaisk.view_lotteryhistory", raise_exception=True)
def lottery_history(request):
    """
    Vue pour afficher l'historique des loteries terminées.
    """
    past_lotteries = Lottery.objects.filter(
        status__in=["completed", "cancelled"]
    ).order_by("-start_date")

    # Pagination (25 loteries par page)
    paginator = Paginator(past_lotteries, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
    }

    return render(request, "fortunaisk/lottery_history.html", context)
