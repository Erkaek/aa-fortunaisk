# fortunaisk/tasks.py

# Standard Library
import json
import logging
import math
import time
from datetime import timedelta

# Third Party
from celery import group, shared_task

# Django
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

# fortunaisk
from fortunaisk.notifications import send_alliance_auth_notification

logger = logging.getLogger(__name__)


def process_payment(payment_locked):
    """
    Process a single payment with multi-ticket logic:
    1. Determine the maximum number of full tickets purchasable.
    2. Enforce maximum tickets per user.
    3. Compute the effective cost and any remainder.
    4. Create or update a TicketPurchase record.
    5. Record an anomaly if there's an overpayment.
    6. (Total pot update is deferred to the finalization phase.)
    7. Mark the payment as processed and send a confirmation.
    8. Immediately recalculate and update the lottery pot.
    """
    ProcessedPayment   = apps.get_model("fortunaisk", "ProcessedPayment")
    TicketAnomaly      = apps.get_model("fortunaisk", "TicketAnomaly")
    Lottery            = apps.get_model("fortunaisk", "Lottery")
    EveCharacter       = apps.get_model("eveonline", "EveCharacter")
    CharacterOwnership = apps.get_model("authentication", "CharacterOwnership")
    UserProfile        = apps.get_model("authentication", "UserProfile")
    TicketPurchase     = apps.get_model("fortunaisk", "TicketPurchase")

    payment_id     = payment_locked.entry_id
    payment_date   = payment_locked.date
    payment_amount = payment_locked.amount
    lottery_ref    = payment_locked.reason.strip().lower()

    # Skip if already processed.
    if ProcessedPayment.objects.filter(payment_id=payment_id).exists():
        logger.debug(f"Payment ID {payment_id} already processed. Skipping.")
        return

    # Step 1: Retrieve user and character
    try:
        eve_character       = EveCharacter.objects.get(
            character_id=payment_locked.first_party_name_id
        )
        ownership           = CharacterOwnership.objects.get(
            character__character_id=eve_character.character_id
        )
        user_profile        = UserProfile.objects.get(
            user_id=ownership.user_id
        )
        user                = user_profile.user
    except EveCharacter.DoesNotExist:
        TicketAnomaly.objects.create(
            lottery=None, user=None, character=None,
            reason="EveCharacter does not exist",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        return
    except CharacterOwnership.DoesNotExist:
        TicketAnomaly.objects.create(
            lottery=None, user=None, character=eve_character,
            reason="CharacterOwnership does not exist",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        return
    except UserProfile.DoesNotExist:
        TicketAnomaly.objects.create(
            lottery=None, user=None, character=eve_character,
            reason="UserProfile does not exist",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        return

    # Step 2: Retrieve the active lottery
    try:
        lottery = Lottery.objects.select_for_update().get(
            lottery_reference=lottery_ref,
            status__in=["active", "pending"]
        )
    except Lottery.DoesNotExist:
        TicketAnomaly.objects.create(
            lottery=None, user=user, character=eve_character,
            reason=f"No active lottery '{lottery_ref}'",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        return

    # Step 3: Verify that the payment date is within the lottery period
    if not (lottery.start_date <= payment_date <= lottery.end_date):
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=eve_character,
            reason="Payment date outside lottery period",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        return

    # Step 4: Calculate the maximum full tickets purchasable
    ticket_price = lottery.ticket_price
    num_tickets  = math.floor(payment_amount / ticket_price)
    if num_tickets < 1:
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=eve_character,
            reason="Insufficient amount for one ticket",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        return

    # Step 5: Adjust for maximum tickets per user
    current_tickets = (
        TicketPurchase.objects.filter(
            lottery=lottery,
            user=user,
            character__id=user_profile.main_character_id
        ).aggregate(total=Sum("quantity"))["total"] or 0
    )
    allowed_tickets = (
        lottery.max_tickets_per_user - current_tickets
        if lottery.max_tickets_per_user else num_tickets
    )
    final_tickets = min(num_tickets, allowed_tickets)
    if final_tickets < 1:
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=eve_character,
            reason="Max tickets per user exceeded",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id
        )
        ProcessedPayment.objects.create(
            payment_id=payment_id,
            processed_at=timezone.now()
        )
        send_alliance_auth_notification(
            user=user,
            title="⚠️ Ticket Limit Reached",
            message=(
                f"Hello {user.username},\n\n"
                f"You have reached the maximum number of tickets "
                f"({lottery.max_tickets_per_user}) for lottery "
                f"'{lottery.lottery_reference}'."
            ),
            level="warning"
        )
        return

    # Step 6: Create or update the TicketPurchase record
    cost = final_tickets * ticket_price
    purchase, created = TicketPurchase.objects.get_or_create(
        lottery=lottery,
        user=user,
        character=eve_character,
        defaults={
            "amount": cost,
            "quantity": final_tickets,
            "status": "processed",
            "payment_id": payment_id,
        },
    )
    if not created:
        purchase.quantity      += final_tickets
        purchase.amount        += cost
        purchase.payment_id     = payment_id
        purchase.save(update_fields=["quantity", "amount", "payment_id"])

    # Step 7: Record an anomaly if there's an overpayment
    remainder = payment_amount - cost
    if remainder > 0:
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=eve_character,
            reason=f"Overpayment of {remainder} ISK",
            payment_date=payment_date, amount=remainder,
            payment_id=payment_id
        )

    # Step 8: Mark the payment as processed and send confirmation
    ProcessedPayment.objects.create(
        payment_id=payment_id,
        processed_at=timezone.now()
    )
    message = (
        f"Hello {user.username},\n\n"
        f"Your payment of {payment_amount} ISK has been processed for lottery "
        f"'{lottery.lottery_reference}'. You purchased {final_tickets} ticket(s)."
    )
    if remainder > 0:
        message += f"\nAn overpayment of {remainder} ISK was recorded."
    message += "\nGood luck!"
    send_alliance_auth_notification(
        user=user,
        title="🍀 Ticket Purchase Confirmation",
        message=message,
        level="info"
    )

    # Step 9: Immediately recalculate and update the pot
    total_pot = (
        TicketPurchase.objects
        .filter(lottery=lottery)
        .aggregate(sum=Sum("amount"))["sum"] or 0
    )
    lottery.total_pot = total_pot
    lottery.save(update_fields=["total_pot"])


@shared_task(bind=True)
def process_payment_task(self, payment_entry_id):
    """
    Asynchronously process a single payment identified by its entry_id.
    """
    CorpJournal = apps.get_model("corptools", "CorporationWalletJournalEntry")
    try:
        with transaction.atomic():
            entry = CorpJournal.objects.select_for_update().get(entry_id=payment_entry_id)
            process_payment(entry)
    except Exception as e:
        logger.error(f"Error in process_payment_task for {payment_entry_id}: {e}", exc_info=True)
        raise


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Dispatches processing tasks for all new lottery payments.
    """
    logger.info("Starting 'check_purchased_tickets' task.")
    CorpJournal  = apps.get_model("corptools", "CorporationWalletJournalEntry")
    ProcessedPay = apps.get_model("fortunaisk", "ProcessedPayment")

    processed_ids = set(ProcessedPay.objects.values_list("payment_id", flat=True))
    pending = CorpJournal.objects.filter(
        reason__icontains="lottery",
        amount__gt=0
    ).exclude(entry_id__in=processed_ids)

    if pending.exists():
        tasks = [process_payment_task.s(p.entry_id) for p in pending]
        group(tasks).apply_async()


@shared_task(bind=True, max_retries=5)
def check_lottery_status(self):
    """
    Close lotteries only after 'Corporation Audit Update' has run + 5 min safety.
    """
    lock_id = "check_lottery_status_lock"
    if not cache.add(lock_id, "1", timeout=300):
        return

    try:
        try:
            audit    = PeriodicTask.objects.get(name="Corporation Audit Update")
            last_run = audit.last_run_at
        except PeriodicTask.DoesNotExist:
            logger.warning("Audit task 'Corporation Audit Update' not found. Delaying closure.")
            return

        if not last_run or timezone.now() < last_run + timedelta(minutes=5):
            logger.info("Waiting safety interval after audit before closing lotteries.")
            return

        Lottery      = apps.get_model("fortunaisk", "Lottery")
        CorpJournal  = apps.get_model("corptools", "CorporationWalletJournalEntry")
        ProcessedPay = apps.get_model("fortunaisk", "ProcessedPayment")

        to_close = Lottery.objects.filter(
            status__in=["active", "pending"],
            end_date__lte=last_run
        )

        for lot in to_close:
            if lot.status == "active":
                lot.status = "pending"
                lot.save(update_fields=["status"])

            unpaid = CorpJournal.objects.filter(
                reason__iexact=lot.lottery_reference.lower(),
                amount__gt=0,
                date__lte=last_run
            ).exclude(
                entry_id__in=ProcessedPay.objects.values_list("payment_id", flat=True)
            )

            if unpaid.exists():
                logger.info(f"Unprocessed payments for '{lot.lottery_reference}'; retrying later.")
                check_purchased_tickets.delay()
                continue

            TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
            total = (
                TicketPurchase.objects
                .filter(lottery=lot)
                .aggregate(sum=Sum("amount"))["sum"] or 0
            )
            lot.total_pot = total
            lot.status    = "completed"
            lot.save(update_fields=["total_pot", "status"])

            if total > 0:
                winners = lot.select_winners()
                logger.info(f"{len(winners)} winner(s) for '{lot.lottery_reference}'.")
            else:
                logger.error(f"No pot for '{lot.lottery_reference}', no winners.")
    finally:
        cache.delete(lock_id)


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_lottery_id: int):
    """
    Creates a Lottery based on a specific AutoLottery.
    """
    logger.info(f"Starting 'create_lottery_from_auto_lottery' for AutoLottery ID {auto_lottery_id}.")
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto    = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        new_lot = auto.create_lottery()
        logger.info(f"Created Lottery '{new_lot.lottery_reference}' (ID {new_lot.id}).")
        return new_lot.id
    except Exception as e:
        logger.error(f"Error in create_lottery_from_auto_lottery: {e}", exc_info=True)
        return None


@shared_task(bind=True)
def finalize_lottery(self, lottery_id: int):
    """
    Finalizes a Lottery once it has ended: selects winners, updates status.
    """
    logger.info(f"Starting 'finalize_lottery' for Lottery ID {lottery_id}.")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lot = Lottery.objects.get(id=lottery_id)
        if lot.status not in ["active", "pending"]:
            return
        winners = lot.select_winners()
        lot.status = "completed"
        lot.save(update_fields=["status"])
        if winners:
            logger.info(f"{len(winners)} winner(s) for '{lot.lottery_reference}'.")
        else:
            logger.warning(f"No winners for '{lot.lottery_reference}'.")
    except Exception as e:
        logger.error(f"Error in finalize_lottery: {e}", exc_info=True)
        try:
            self.retry(exc=e, countdown=60, max_retries=3)
        except self.MaxRetriesExceededError:
            logger.error("Max retries exceeded for finalize_lottery.")


def setup_periodic_tasks():
    """
    Configures global periodic tasks:
      - check_purchased_tickets (every 30 minutes)
      - check_lottery_status     (every  2 minutes)
    """
    logger.info("Configuring global periodic tasks for FortunaIsk.")
    try:
        IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
        PeriodicTask    = apps.get_model("django_celery_beat", "PeriodicTask")

        sched_30m, _ = IntervalSchedule.objects.get_or_create(
            every=30, period=IntervalSchedule.minutes
        )
        PeriodicTask.objects.update_or_create(
            name="check_purchased_tickets",
            defaults={
                "task": "fortunaisk.tasks.check_purchased_tickets",
                "interval": sched_30m,
                "args": json.dumps([]),
                "enabled": True,
            },
        )

        sched_2m, _ = IntervalSchedule.objects.get_or_create(
            every=2, period=IntervalSchedule.minutes
        )
        PeriodicTask.objects.update_or_create(
            name="check_lottery_status",
            defaults={
                "task": "fortunaisk.tasks.check_lottery_status",
                "interval": sched_2m,
                "args": json.dumps([]),
                "enabled": True,
            },
        )

        logger.info("Periodic tasks 'check_purchased_tickets' & 'check_lottery_status' configured.")
    except Exception as e:
        logger.critical(f"Error configuring periodic tasks: {e}", exc_info=True)
