"""Celery tasks for the FortunaIsk lottery application with multiple winners and Discord notifications."""

# Standard Library
import json
import logging
from datetime import timedelta
from random import shuffle

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import AutoLottery, Lottery, TicketAnomaly, TicketPurchase, Winner
from .notifications import send_discord_webhook  # Import from notifications.py

logger = logging.getLogger(__name__)


def send_discord_dm(user, message):
    """
    Send a DM to the given user on Discord.
    TODO: Implement actual DM sending logic if user Discord ID is known.
    """
    # Placeholder for actual implementation.
    pass


@shared_task
def check_lotteries():
    """
    Check all active lotteries that have passed their end date and select winners.
    """
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
    for lottery in active_lotteries:
        select_winners_for_lottery(lottery)


def select_winners_for_lottery(lottery):
    """
    Select multiple winners for the given lottery, distribute pot.
    """
    participants = User.objects.filter(ticketpurchase__lottery=lottery).distinct()
    participant_count = participants.count()

    if participant_count == 0:
        lottery.status = "completed"
        lottery.participant_count = 0
        lottery.total_pot = 0
        lottery.save()
        send_discord_webhook(
            f"Aucune participation pour la loterie {lottery.lottery_reference}. La loterie s'est terminée sans gagnants."
        )
        return

    # Get all ticket amounts
    sum_amount = TicketPurchase.objects.filter(lottery=lottery).values_list(
        "amount", flat=True
    )
    pot = sum(sum_amount) if sum_amount else 0
    lottery.participant_count = participant_count
    lottery.total_pot = pot

    all_tickets = list(TicketPurchase.objects.filter(lottery=lottery))
    shuffle(all_tickets)

    winners_count = lottery.winner_count
    distribution = lottery.winners_distribution or [100]

    chosen_tickets = all_tickets[:winners_count]

    with transaction.atomic():
        for i, ticket in enumerate(chosen_tickets):
            percent = distribution[i]
            prize = (pot * percent) / 100.0
            Winner.objects.create(
                character=ticket.character,
                ticket=ticket,
                won_at=timezone.now(),
                prize_amount=prize,
            )
            send_discord_dm(
                ticket.user,
                f"Félicitations ! Vous avez gagné {prize} ISK dans la loterie {lottery.lottery_reference} !",
            )

    lottery.status = "completed"
    lottery.save()
    send_discord_webhook(
        f"La loterie {lottery.lottery_reference} s'est terminée ! {winners_count} gagnants ont été sélectionnés. Pot total : {pot} ISK."
    )


@shared_task
def process_wallet_tickets():
    """
    Process wallet entries for all active lotteries.
    """
    logger.info("Traitement des entrées de portefeuille pour les loteries actives.")
    active_lotteries = Lottery.objects.filter(status="active")

    if not active_lotteries.exists():
        logger.info("Aucune loterie active trouvée.")
        return "Aucune loterie active à traiter."

    processed_entries = 0
    for lottery in active_lotteries:
        reason_filter = lottery.lottery_reference
        if reason_filter.startswith("LOTTERY-"):
            reason_filter = reason_filter[len("LOTTERY-") :]

        payments = CorporationWalletJournalEntry.objects.filter(
            second_party_name_id=lottery.payment_receiver,
            amount=lottery.ticket_price,
            reason__contains=reason_filter,
        )

        if not payments.exists():
            logger.info(f"Aucun paiement trouvé pour la loterie : {lottery.id}")
            continue

        for payment in payments:
            anomaly_reason = None
            character = None
            user = None
            payment_id = payment.id

            if TicketAnomaly.objects.filter(
                lottery=lottery, payment_id=payment_id
            ).exists():
                logger.info(
                    f"Anomalie déjà enregistrée pour le paiement {payment_id}, passage."
                )
                continue

            if not (lottery.start_date <= payment.date <= lottery.end_date):
                anomaly_reason = (
                    "Date de paiement en dehors de la période de la loterie."
                )

            try:
                character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = character.character_ownership
                if not ownership or not ownership.user:
                    if anomaly_reason is None:
                        anomaly_reason = (
                            "Aucun utilisateur principal pour le personnage."
                        )
                else:
                    user = ownership.user
                    user_ticket_count = TicketPurchase.objects.filter(
                        user=user, lottery=lottery
                    ).count()
                    if user_ticket_count >= lottery.max_tickets_per_user:
                        if anomaly_reason is None:
                            anomaly_reason = f"L'utilisateur '{user.username}' a dépassé le nombre maximum de tickets ({lottery.max_tickets_per_user})."
            except EveCharacter.DoesNotExist:
                if anomaly_reason is None:
                    anomaly_reason = (
                        f"Personnage Eve {payment.first_party_name_id} non trouvé."
                    )

            if anomaly_reason:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=anomaly_reason,
                    payment_date=payment.date,
                    amount=int(payment.amount),
                    payment_id=payment_id,
                )
                logger.info(f"Anomalie détectée : {anomaly_reason}")
                continue

            # No anomaly, create ticket
            try:
                with transaction.atomic():
                    TicketPurchase.objects.create(
                        user=user,
                        lottery=lottery,
                        character=character,
                        amount=int(payment.amount),
                        purchase_date=timezone.now(),
                        payment_id=payment.id,  # Enregistrer l'ID du paiement
                    )
                    logger.info(
                        f"Ticket enregistré pour l'utilisateur '{user.username}'."
                    )
                processed_entries += 1
            except IntegrityError as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Erreur d'intégrité : {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                    payment_id=payment_id,
                )
                logger.error(
                    f"Erreur d'intégrité lors du traitement du paiement {payment.id} : {e}"
                )
            except Exception as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Erreur inattendue : {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                    payment_id=payment.id,
                )
                logger.exception(
                    f"Erreur inattendue lors du traitement du paiement {payment.id} : {e}"
                )

    logger.info(
        f"{processed_entries} tickets traités pour toutes les loteries actives."
    )
    return f"{processed_entries} tickets traités pour toutes les loteries actives."


def setup_tasks(sender, **kwargs):
    # Third Party
    from django_celery_beat.models import IntervalSchedule, PeriodicTask

    task_name_check_lotteries = "FortunaIsk_check_lotteries_status"
    task_name_process_wallet_tickets = "FortunaIsk_process_wallet_tickets"

    schedule, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.HOURS,
    )

    PeriodicTask.objects.update_or_create(
        name=task_name_check_lotteries,
        defaults={
            "task": "fortunaisk.tasks.check_lotteries",
            "interval": schedule,
            "args": json.dumps([]),
        },
    )

    PeriodicTask.objects.update_or_create(
        name=task_name_process_wallet_tickets,
        defaults={
            "task": "fortunaisk.tasks.process_wallet_tickets",
            "interval": schedule,
            "args": json.dumps([]),
        },
    )


@shared_task
def create_lottery_from_auto(auto_lottery_id):
    """
    Crée une nouvelle loterie à partir d'une Auto Lottery.
    """
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id)

        # Créer la nouvelle loterie
        start_date = timezone.now()
        end_date = start_date + timedelta(hours=auto_lottery.duration_hours)

        lottery = Lottery.objects.create(
            ticket_price=auto_lottery.ticket_price,
            start_date=start_date,
            end_date=end_date,
            payment_receiver=auto_lottery.payment_receiver,
            winner_count=auto_lottery.winner_count,
            winners_distribution_str=auto_lottery.winners_distribution_str,
            max_tickets_per_user=auto_lottery.max_tickets_per_user,
        )

        logger.info(
            f"Created new lottery from auto lottery '{auto_lottery.name}' (ID: {auto_lottery_id})"
        )
        return lottery.id

    except AutoLottery.DoesNotExist:
        logger.error(f"Auto Lottery with ID {auto_lottery_id} not found")
    except Exception as e:
        logger.error(
            f"Error creating lottery from auto lottery {auto_lottery_id}: {str(e)}"
        )
