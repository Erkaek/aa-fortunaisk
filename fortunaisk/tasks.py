# fortunaisk/tasks.py
"""Celery tasks for the FortunaIsk lottery application."""

# Standard Library
import json
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import Lottery, TicketAnomaly, TicketPurchase, Winner

logger = logging.getLogger(__name__)


@shared_task
def check_lotteries():
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
    for lottery in active_lotteries:
        select_winner_for_lottery(lottery)


def select_winner_for_lottery(lottery):
    participants = User.objects.filter(ticketpurchase__lottery=lottery).annotate(
        ticket_count=Count("ticketpurchase")
    )

    if not participants.exists():
        logger.info(f"No participants for lottery {lottery.lottery_reference}")
        return

    winner_user = participants.order_by("?").first()
    lottery.winner = winner_user
    lottery.status = "completed"
    lottery.save()

    Winner.objects.create(
        character=winner_user.profile.main_character,
        ticket=TicketPurchase.objects.filter(user=winner_user, lottery=lottery).first(),
        won_at=timezone.now(),
    )

    logger.info(
        f"Winner selected for lottery {lottery.lottery_reference}: {winner_user.username}"
    )


@shared_task
def process_wallet_tickets():
    logger.info("Processing wallet entries for active lotteries.")
    active_lotteries = Lottery.objects.filter(status="active")

    if not active_lotteries.exists():
        logger.info("No active lotteries found.")
        return "No active lotteries to process."

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
            logger.info(f"No payments found for lottery: {lottery.id}")
            continue

        for payment in payments:
            anomaly_reason = None
            character = None
            user = None

            logger.info(
                f"DEBUG: Checking payment date for lottery {lottery.lottery_reference}: "
                f"lottery.start_date={lottery.start_date}, lottery.end_date={lottery.end_date}, "
                f"payment.date={payment.date} (type={type(payment.date)})"
            )
             
            # Vérification de la date de paiement
            if not (lottery.start_date <= payment.date <= lottery.end_date):
                anomaly_reason = "Payment date not within lottery start/end date."

            try:
                character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = character.character_ownership
                if not ownership or not ownership.user:
                    if anomaly_reason is None:
                        anomaly_reason = "No main user for character."
                else:
                    user = ownership.user
                    if user.profile.main_character_id != character.id:
                        if anomaly_reason is None:
                            anomaly_reason = (
                                "Character is not the main character of the user."
                            )
            except EveCharacter.DoesNotExist:
                if anomaly_reason is None:
                    anomaly_reason = (
                        f"EveCharacter with ID {payment.first_party_name_id} not found."
                    )

            if (
                user
                and TicketPurchase.objects.filter(user=user, lottery=lottery).exists()
            ):
                if anomaly_reason is None:
                    anomaly_reason = f"Duplicate ticket for user '{user.username}'."

            if anomaly_reason:
                # Enregistrer l'anomalie
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=anomaly_reason,
                    payment_date=payment.date,
                    amount=int(payment.amount),
                )
                logger.info(f"Anomaly detected: {anomaly_reason}")
                continue

            # Si aucune anomalie, création du ticket
            try:
                with transaction.atomic():
                    TicketPurchase.objects.create(
                        user=user,
                        lottery=lottery,
                        character=character,
                        amount=int(payment.amount),
                        purchase_date=timezone.now(),
                    )
                    logger.info(f"Ticket registered for user '{user.username}'.")
                processed_entries += 1
            except IntegrityError as e:
                # En cas d'erreur d'intégrité, on enregistre une anomalie
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Integrity error: {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                )
                logger.error(f"Integrity error processing payment {payment.id}: {e}")
            except Exception as e:
                # Toute autre exception, également enregistrer une anomalie
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Unexpected error: {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                )
                logger.exception(
                    f"Unexpected error processing payment {payment.id}: {e}"
                )

    logger.info(f"Processed {processed_entries} tickets across active lotteries.")
    return f"Processed {processed_entries} tickets for all active lotteries."


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
