# fortunaisk/tasks.py

# Standard Library
import logging

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry

# Django
from django.db import IntegrityError, transaction
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

# fortunaisk
from fortunaisk.models import AutoLottery, Lottery, TicketAnomaly, TicketPurchase

logger = logging.getLogger(__name__)


def send_discord_dm(user, message: str) -> None:
    """
    Sends a DM to the user on Discord.
    TODO: Implement actual logic if the user's Discord ID is known.
    """
    pass


@shared_task
def check_lotteries() -> str:
    """
    Checks all active lotteries that have passed their end date and completes them.
    """
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
    count = active_lotteries.count()
    for lottery in active_lotteries:
        lottery.complete_lottery()
    return f"Checked {count} lotteries."


@shared_task
def create_lottery_from_auto(auto_lottery_id: int) -> int | None:
    """
    Creates a new Lottery from an AutoLottery (Celery scheduled).
    """
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id)

        start_date = timezone.now()
        end_date = start_date + auto_lottery.get_duration_timedelta()

        new_lottery = Lottery.objects.create(
            ticket_price=auto_lottery.ticket_price,
            start_date=start_date,
            end_date=end_date,
            payment_receiver=auto_lottery.payment_receiver,
            winner_count=auto_lottery.winner_count,
            winners_distribution=auto_lottery.winners_distribution,
            max_tickets_per_user=auto_lottery.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=auto_lottery.duration_value,
            duration_unit=auto_lottery.duration_unit,
        )
        logger.info(
            f"Created new Lottery '{new_lottery.lottery_reference}' "
            f"from AutoLottery '{auto_lottery.name}' (ID: {auto_lottery_id})"
        )
        return new_lottery.id

    except AutoLottery.DoesNotExist:
        logger.error(f"AutoLottery with ID {auto_lottery_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Error creating Lottery from AutoLottery {auto_lottery_id}: {str(e)}"
        )
    return None


@shared_task
def process_wallet_tickets() -> str:
    """
    Processes wallet entries for all active lotteries.
    Matches CorporationWalletJournalEntry entries to create TicketPurchase or anomalies.
    """
    logger.info("Processing wallet entries for active lotteries.")
    active_lotteries = Lottery.objects.filter(status="active")
    total_processed = 0

    if not active_lotteries.exists():
        return "No active lotteries to process."

    for lottery in active_lotteries:
        reason_filter = ""
        if lottery.lottery_reference:
            # e.g. "LOTTERY-123456" => reason might contain "123456"
            reason_filter = lottery.lottery_reference.replace("LOTTERY-", "")

        # Strict match on amount and partial match on reason
        payments = CorporationWalletJournalEntry.objects.filter(
            second_party_name_id=lottery.payment_receiver,
            amount=lottery.ticket_price,  # Ensure amount matches ticket_price
            reason__icontains=reason_filter,
        ).select_related("first_party_name")

        for payment in payments:
            # Identify potential anomalies
            anomaly_reason = None
            eve_character = None
            user = None
            payment_id_str = str(payment.id)

            # Check if anomaly is already recorded
            if TicketAnomaly.objects.filter(
                lottery=lottery, payment_id=payment_id_str
            ).exists():
                logger.info(
                    f"Anomaly already recorded for payment {payment_id_str}, skipping."
                )
                continue

            # Check date range
            if not (lottery.start_date <= payment.date <= lottery.end_date):
                anomaly_reason = "Payment date outside lottery period."

            # Identify character
            try:
                eve_character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = eve_character.character_ownership
                if not ownership or not ownership.user:
                    if anomaly_reason is None:
                        anomaly_reason = "No primary user for the character."
                else:
                    user = ownership.user
                    # Check max tickets per user
                    user_ticket_count = TicketPurchase.objects.filter(
                        user=user, lottery=lottery
                    ).count()
                    if lottery.max_tickets_per_user is not None:
                        if user_ticket_count >= lottery.max_tickets_per_user:
                            if anomaly_reason is None:
                                anomaly_reason = (
                                    f"User '{user.username}' exceeded the max tickets "
                                    f"({lottery.max_tickets_per_user})."
                                )
            except EveCharacter.DoesNotExist:
                if anomaly_reason is None:
                    anomaly_reason = (
                        f"EveCharacter {payment.first_party_name_id} not found."
                    )

            # Record anomaly if found
            if anomaly_reason:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=anomaly_reason,
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                logger.info(f"Anomaly detected: {anomaly_reason}")
                continue

            # Otherwise, create the TicketPurchase with correct amount
            try:
                with transaction.atomic():
                    TicketPurchase.objects.create(
                        user=user,
                        lottery=lottery,
                        character=eve_character,
                        amount=lottery.ticket_price,  # Set amount to ticket_price
                        purchase_date=timezone.now(),
                        payment_id=payment_id_str,
                    )
                    logger.info(f"Ticket recorded for user '{user.username}'.")
                total_processed += 1
            except IntegrityError as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=f"Integrity error: {e}",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                logger.error(
                    f"Integrity error while processing payment {payment_id_str}: {e}"
                )
            except Exception as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=f"Unexpected error: {e}",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                logger.exception(
                    f"Unexpected error while processing payment {payment_id_str}: {e}"
                )

    return f"{total_processed} tickets processed for all active lotteries."
