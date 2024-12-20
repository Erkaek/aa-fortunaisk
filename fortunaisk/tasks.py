# fortunaisk/tasks.py
"""Celery tasks for the FortunaIsk lottery application with multiple winners and Discord notifications."""

# Standard Library
import json
import logging
from random import shuffle

# Third Party
import requests
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import Lottery, LotterySettings, TicketAnomaly, TicketPurchase, Winner, AutoLottery

logger = logging.getLogger(__name__)


def send_discord_webhook(message):
    """
    Send a message to the configured Discord webhook.
    """
    settings = LotterySettings.objects.get_or_create()[0]
    if not settings.discord_webhook:
        return
    payload = {"content": message}
    try:
        requests.post(settings.discord_webhook, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"Failed to send Discord webhook: {e}")


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
            f"No participants for lottery {lottery.lottery_reference}. Lottery ended with no winners."
        )
        return

    # Récupérer tous les montants de tickets
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
        f"Lottery {lottery.lottery_reference} ended! {winners_count} winners selected. Total pot: {pot} ISK."
    )


@shared_task
def process_wallet_tickets():
    """
    Process wallet entries for all active lotteries.
    """
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
            payment_id = payment.id

            if TicketAnomaly.objects.filter(
                lottery=lottery, payment_id=payment_id
            ).exists():
                logger.info(
                    f"Anomaly already recorded for payment {payment_id}, skipping."
                )
                continue

            if not (lottery.start_date <= payment.date <= lottery.end_date):
                anomaly_reason = "Payment date not within lottery timeframe."

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
                    user_ticket_count = TicketPurchase.objects.filter(
                        user=user, lottery=lottery
                    ).count()
                    if user_ticket_count >= lottery.max_tickets_per_user:
                        if anomaly_reason is None:
                            anomaly_reason = f"User '{user.username}' exceeded max tickets ({lottery.max_tickets_per_user})."
            except EveCharacter.DoesNotExist:
                if anomaly_reason is None:
                    anomaly_reason = (
                        f"EveCharacter {payment.first_party_name_id} not found."
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
                logger.info(f"Anomaly detected: {anomaly_reason}")
                continue

            # No anomaly, create the ticket
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
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Integrity error: {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                    payment_id=payment_id,
                )
                logger.error(f"Integrity error processing payment {payment.id}: {e}")
            except Exception as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Unexpected error: {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                    payment_id=payment_id,
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

def create_lottery_from_auto(autolottery_id):
    """
    Task to create a lottery based on an AutoLottery configuration.
    """
    try:
        autolottery = AutoLottery.objects.get(id=autolottery_id, is_active=True)
    except AutoLottery.DoesNotExist:
        logger.warning(f"AutoLottery with ID {autolottery_id} does not exist or is inactive.")
        return

    # Créer une nouvelle loterie basée sur les paramètres de AutoLottery
    lottery = Lottery(
        ticket_price=autolottery.ticket_price,
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(hours=autolottery.duration_hours),
        payment_receiver=autolottery.payment_receiver,
        winner_count=autolottery.winner_count,
        winners_distribution_str=autolottery.winners_distribution_str,
        max_tickets_per_user=autolottery.max_tickets_per_user,
    )
    lottery.lottery_reference = lottery.generate_unique_reference()
    lottery.save()

    logger.info(f"Automatic Lottery '{autolottery.name}' created with reference {lottery.lottery_reference}.")

    # Optionnel : Envoyer une notification ou effectuer d'autres actions