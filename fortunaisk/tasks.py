# fortunaisk/tasks.py

import json
import logging
import math
from datetime import timedelta

from celery import group, shared_task
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .notifications import (
    send_ticket_purchase_confirmation_dm,
    send_ticket_anomaly_dm,
    send_winner_dm,
    send_webhook_notification,
    create_lottery_completed_with_winners_embed,
    create_lottery_completed_no_winner_embed,
)

logger = logging.getLogger(__name__)


def process_payment(entry):
    """
    Process a single payment entry:
      1. Identify user & character
      2. Load the active lottery
      3. Validate date
      4. Calculate tickets purchasable
      5. Enforce per-user max
      6. Create/update TicketPurchase
      7. Record overpayment anomaly
      8. Mark processed & send DM
      9. Update lottery pot
    """
    # Models
    CorpJournal     = apps.get_model("corptools", "CorporationWalletJournalEntry")
    ProcessedPay    = apps.get_model("fortunaisk", "ProcessedPayment")
    TicketAnomaly   = apps.get_model("fortunaisk", "TicketAnomaly")
    Lottery         = apps.get_model("fortunaisk", "Lottery")
    EveCharacter    = apps.get_model("eveonline", "EveCharacter")
    Ownership       = apps.get_model("authentication", "CharacterOwnership")
    UserProfile     = apps.get_model("authentication", "UserProfile")
    TicketPurchase  = apps.get_model("fortunaisk", "TicketPurchase")

    pid    = entry.entry_id
    date   = entry.date
    amount = entry.amount
    ref    = entry.reason.strip().lower()

    # 1) Skip if already processed
    if ProcessedPay.objects.filter(payment_id=pid).exists():
        logger.debug(f"Payment {pid} already processed.")
        return

    # 2) Retrieve user & discord_id
    try:
        char    = EveCharacter.objects.get(character_id=entry.first_party_name_id)
        own     = Ownership.objects.get(character=char)
        profile = UserProfile.objects.get(user_id=own.user_id)
        user    = profile.user
        discord_id = user.discord_id
    except Exception as e:
        # cannot DM if user lookup fails
        logger.warning(f"Could not resolve user for payment {pid}: {e}")
        ProcessedPay.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 3) Load active lottery
    try:
        lottery = Lottery.objects.select_for_update().get(
            lottery_reference=ref,
            status__in=["active", "pending"]
        )
    except Lottery.DoesNotExist:
        msg = f"No active lottery '{ref}'"
        TicketAnomaly.objects.create(
            lottery=None, user=user, character=char,
            reason=msg, payment_date=date,
            amount=amount, payment_id=pid
        )
        send_ticket_anomaly_dm(discord_id, ref, msg, amount)
        ProcessedPay.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 4) Date validation
    if not (lottery.start_date <= date <= lottery.end_date):
        msg = "Outside lottery period"
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=char,
            reason=msg, payment_date=date,
            amount=amount, payment_id=pid
        )
        send_ticket_anomaly_dm(discord_id, ref, msg, amount)
        ProcessedPay.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 5) Calculate ticket count
    price       = lottery.ticket_price
    num_tickets = math.floor(amount / price)
    if num_tickets < 1:
        msg = "Insufficient amount for one ticket"
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=char,
            reason=msg, payment_date=date,
            amount=amount, payment_id=pid
        )
        send_ticket_anomaly_dm(discord_id, ref, msg, amount)
        ProcessedPay.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 6) Enforce max tickets per user
    current = TicketPurchase.objects.filter(
        lottery=lottery, user=user, character=char
    ).aggregate(total=Sum("quantity"))["total"] or 0
    if lottery.max_tickets_per_user:
        allowed = lottery.max_tickets_per_user - current
    else:
        allowed = num_tickets
    final = min(num_tickets, allowed)
    if final < 1:
        msg = "User ticket limit reached"
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=char,
            reason=msg, payment_date=date,
            amount=amount, payment_id=pid
        )
        send_ticket_anomaly_dm(discord_id, ref, msg, amount)
        ProcessedPay.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 7) Create or update TicketPurchase
    cost = final * price
    purchase, created = TicketPurchase.objects.get_or_create(
        lottery=lottery,
        user=user,
        character=char,
        defaults={
            "amount": cost,
            "quantity": final,
            "status": "processed",
            "payment_id": pid,
        },
    )
    if not created:
        purchase.quantity += final
        purchase.amount   += cost
        purchase.save(update_fields=["quantity", "amount"])

    # 8) Handle overpayment
    remainder = amount - cost
    if remainder > 0:
        msg = f"Overpayment of {remainder} ISK"
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=char,
            reason=msg, payment_date=date,
            amount=remainder, payment_id=pid
        )
        send_ticket_anomaly_dm(discord_id, ref, msg, remainder)

    # 9) Mark processed & send confirmation DM
    ProcessedPay.objects.create(payment_id=pid, processed_at=timezone.now())
    send_ticket_purchase_confirmation_dm(discord_id, ref, final, cost, remainder)

    # 10) Update lottery total pot
    total_pot = TicketPurchase.objects.filter(lottery=lottery).aggregate(
        sum=Sum("amount")
    )["sum"] or 0
    lottery.total_pot = total_pot
    lottery.save(update_fields=["total_pot"])


@shared_task(bind=True)
def process_payment_task(self, payment_entry_id):
    """
    Wrap process_payment in a DB transaction.
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
    Every 30 minutes: find new payments and dispatch processing tasks.
    """
    logger.info("Starting 'check_purchased_tickets'.")
    CorpJournal = apps.get_model("corptools", "CorporationWalletJournalEntry")
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
    Every 2 minutes: finalize pending lotteries after Corporation Audit Update + 5min safety,
    DM winners & post webhook embed.
    """
    lock_id = "check_lottery_status_lock"
    if not cache.add(lock_id, "1", timeout=300):
        return

    try:
        PeriodicTask = apps.get_model("django_celery_beat", "PeriodicTask")
        audit = PeriodicTask.objects.get(name="Corporation Audit Update")
        last_run = audit.last_run_at
    except PeriodicTask.DoesNotExist:
        logger.warning("Audit task not found. Delaying lottery closure.")
        return

    if not last_run or timezone.now() < last_run + timedelta(minutes=5):
        logger.info("Waiting safety interval after audit before closing lotteries.")
        return

    Lottery    = apps.get_model("fortunaisk", "Lottery")
    CorpJournal= apps.get_model("corptools", "CorporationWalletJournalEntry")
    ProcessedPay = apps.get_model("fortunaisk", "ProcessedPayment")
    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")

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
        ).exclude(entry_id__in=ProcessedPay.objects.values_list("payment_id", flat=True))

        if unpaid.exists():
            logger.info(f"Found unprocessed payments for '{lot.lottery_reference}', retrying.")
            check_purchased_tickets.delay()
            continue

        # Finalize lottery
        total = TicketPurchase.objects.filter(lottery=lot).aggregate(sum=Sum("amount"))["sum"] or 0
        lot.total_pot = total
        lot.status    = "completed"
        lot.save(update_fields=["total_pot", "status"])

        # Notify winners or no-winner
        if total > 0:
            winners = lot.select_winners()
            for w in winners:
                send_winner_dm(
                    discord_user_id=w.ticket.user.discord_id,
                    lottery_ref=lot.lottery_reference,
                    prize_amount=w.prize_amount,
                    ticket_id=w.ticket.id
                )
            embed = create_lottery_completed_with_winners_embed(lot, winners)
        else:
            embed = create_lottery_completed_no_winner_embed(lot)

        send_webhook_notification(embed=embed)

    cache.delete(lock_id)


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_lottery_id: int):
    """
    Creates a Lottery based on an AutoLottery.
    The post_save signal will emit the creation webhook.
    """
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        new_lot = auto.create_lottery()
        logger.info(f"Created lottery '{new_lot.lottery_reference}' from AutoLottery #{auto_lottery_id}.")
        return new_lot.id
    except Exception as e:
        logger.error(f"Error in create_lottery_from_auto_lottery: {e}", exc_info=True)
        return None


@shared_task(bind=True)
def finalize_lottery(self, lottery_id: int):
    """
    Finalizes a single Lottery: selects winners, DMs them, posts webhook embed.
    """
    logger.info(f"Finalizing Lottery ID {lottery_id}.")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lot = Lottery.objects.get(id=lottery_id)
        if lot.status not in ["active", "pending"]:
            return

        winners = lot.select_winners()
        lot.status = "completed"
        lot.save(update_fields=["status"])

        if winners:
            for w in winners:
                send_winner_dm(
                    discord_user_id=w.ticket.user.discord_id,
                    lottery_ref=lot.lottery_reference,
                    prize_amount=w.prize_amount,
                    ticket_id=w.ticket.id
                )
            embed = create_lottery_completed_with_winners_embed(lot, winners)
        else:
            embed = create_lottery_completed_no_winner_embed(lot)

        send_webhook_notification(embed=embed)

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
      - check_lottery_status     (every 2 minutes)
    """
    logger.info("Configuring global periodic tasks for FortunaIsk.")
    IntervalSchedule = apps.get_model("django_celery_beat", "IntervalSchedule")
    PeriodicTask     = apps.get_model("django_celery_beat", "PeriodicTask")

    sched_30m, _ = IntervalSchedule.objects.get_or_create(
        every=30, period=IntervalSchedule.MINUTES
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
        every=2, period=IntervalSchedule.MINUTES
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
