# fortunaisk/tasks.py
"""Celery tasks for the FortunaIsk lottery application."""

# Standard Library
import json
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import Lottery, TicketPurchase, Winner

logger = logging.getLogger(__name__)


@shared_task
def check_lotteries():
    """
    Check all lotteries that have passed their end_date and are still active.
    If so, select a winner and mark them as completed.
    """
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)

    for lottery in active_lotteries:
        select_winner_for_lottery(lottery)


def select_winner_for_lottery(lottery):
    """
    Select a winner randomly among the participants of a given lottery.
    """
    # Django
    from django.contrib.auth.models import User

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
    """
    Process all wallet entries from the corporation's journal to register new
    ticket purchases for all active lotteries.
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
            try:
                character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = character.character_ownership
                if not ownership or not ownership.user:
                    logger.warning(
                        f"No main user for character {character.character_name} (ID: {character.character_id})."
                    )
                    continue

                user = ownership.user
                if user.profile.main_character_id != character.id:
                    logger.warning(
                        f"Character {character.character_name} is not the main character of user {user.username}."
                    )
                    continue

                if TicketPurchase.objects.filter(user=user, lottery=lottery).exists():
                    logger.info(
                        f"Duplicate ticket for user '{user.username}', skipping."
                    )
                    continue

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

            except EveCharacter.DoesNotExist:
                logger.error(
                    f"EveCharacter with ID {payment.first_party_name_id} not found."
                )
            except IntegrityError as e:
                logger.error(f"Integrity error processing payment {payment.id}: {e}")
            except Exception as e:
                logger.exception(
                    f"Unexpected error processing payment {payment.id}: {e}"
                )

    logger.info(f"Processed {processed_entries} tickets across active lotteries.")
    return f"Processed {processed_entries} tickets for all active lotteries."


def setup_tasks(sender, **kwargs):
    """
    Setup periodic tasks for checking lotteries and processing wallet tickets.
    This is connected to the post_migrate signal in apps.py.
    """
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
