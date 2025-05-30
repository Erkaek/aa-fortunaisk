# fortunaisk/tasks.py

# Standard Library
import json
import logging
import math
from datetime import timedelta
from decimal import Decimal

# Third Party
from celery import group, shared_task
from django_celery_beat.models import CrontabSchedule, PeriodicTask

# Django
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

# fortunaisk
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)


def process_payment(entry):
    """
    Process a single wallet payment into lottery tickets.

    This function handles the core business logic for ticket purchases:
    - Validates the payment record against existing lotteries
    - Handles character and user identification
    - Enforces ticket limits and lottery status rules
    - Creates ticket purchases and records anomalies when needed
    - Updates the lottery's total pot

    Args:
        entry: CorporationWalletJournalEntry object representing the payment
    """
    ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")
    TicketAnomaly = apps.get_model("fortunaisk", "TicketAnomaly")
    LotteryModel = apps.get_model("fortunaisk", "Lottery")
    EveCharacter = apps.get_model("eveonline", "EveCharacter")
    CharacterOwnership = apps.get_model("authentication", "CharacterOwnership")
    UserProfile = apps.get_model("authentication", "UserProfile")
    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")

    pid = entry.entry_id
    date = entry.date
    amt = entry.amount
    ref = entry.reason.strip()

    # 0) Skip if already processed
    if ProcessedPayment.objects.filter(payment_id=pid).exists():
        logger.debug(f"Payment {pid} already processed, skipping.")
        return

    # 1) Identify user & character
    try:
        char = EveCharacter.objects.get(character_id=entry.first_party_name_id)
        ownership = CharacterOwnership.objects.get(
            character__character_id=char.character_id
        )
        profile = UserProfile.objects.get(user_id=ownership.user_id)
        user = profile.user
    except Exception as e:
        reason = " | ".join(
            filter(
                None,
                [
                    (
                        "EveCharacter missing"
                        if isinstance(e, EveCharacter.DoesNotExist)
                        else ""
                    ),
                    (
                        "Ownership missing"
                        if isinstance(e, CharacterOwnership.DoesNotExist)
                        else ""
                    ),
                    (
                        "Profile missing"
                        if isinstance(e, UserProfile.DoesNotExist)
                        else ""
                    ),
                ],
            )
        ) or str(e)
        TicketAnomaly.objects.create(
            lottery=None,
            user=None,
            character=None,
            reason=reason,
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(
            payment_id=pid,
            character=locals().get("char"),
            user=locals().get("user"),
            amount=amt,
            payed_at=date,
        )
        return

    # 2) Retrieve lottery (any status)
    try:
        lot = LotteryModel.objects.select_for_update().get(
            lottery_reference__iexact=ref
        )
    except LotteryModel.DoesNotExist:
        TicketAnomaly.objects.create(
            lottery=None,
            user=user,
            character=char,
            reason=f"No lottery found with reference '{ref}'",
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(
            payment_id=pid,
            character=char,
            user=user,
            amount=amt,
            payed_at=date,
        )
        return

    # 3) Anomaly if completed/cancelled
    if lot.status in ("completed", "cancelled"):
        reason = (
            "Lottery already completed"
            if lot.status == "completed"
            else "Lottery has been cancelled"
        )
        TicketAnomaly.objects.create(
            lottery=lot,
            user=user,
            character=char,
            reason=reason,
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(
            payment_id=pid,
            character=char,
            user=user,
            amount=amt,
            payed_at=date,
        )
        return

    # 4) Out-of-window payment
    if not (lot.start_date <= date <= lot.end_date):
        TicketAnomaly.objects.create(
            lottery=lot,
            user=user,
            character=char,
            reason="Payment outside lottery period",
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(
            payment_id=pid,
            character=char,
            user=user,
            amount=amt,
            payed_at=date,
        )
        return

    # 5) Compute ticket count
    price = lot.ticket_price
    count = math.floor(amt / price)
    if count < 1:
        TicketAnomaly.objects.create(
            lottery=lot,
            user=user,
            character=char,
            reason="Insufficient funds for one ticket",
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(
            payment_id=pid,
            character=char,
            user=user,
            amount=amt,
            payed_at=date,
        )
        return

    # 6) Enforce per-user limit
    existing = (
        TicketPurchase.objects.filter(
            lottery=lot, user=user, character__id=profile.main_character_id
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    final = (
        count
        if lot.max_tickets_per_user is None
        else min(count, max(0, lot.max_tickets_per_user - existing))
    )
    if final < 1:
        TicketAnomaly.objects.create(
            lottery=lot,
            user=user,
            character=char,
            reason="Ticket limit exceeded",
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(
            payment_id=pid,
            character=char,
            user=user,
            amount=amt,
            payed_at=date,
        )
        notify_discord_or_fallback(
            user=[user],
            event="ticket_limit_reached",
            title="⚠️ Ticket Limit Reached",
            message=(
                f"You have reached the ticket limit "
                f"({lot.max_tickets_per_user}) for lottery {lot.lottery_reference}."
            ),
            level="warning",
            private=True,
        )
        return

    # 7) Create or update TicketPurchase
    gross_cost = price * final
    purchase, created = TicketPurchase.objects.get_or_create(
        lottery=lot,
        user=user,
        character=char,
        defaults={
            "quantity": final,
            "amount": gross_cost,
            "status": "processed",
            "payment_id": pid,
        },
    )
    if not created:
        purchase.quantity += final
        purchase.amount += gross_cost
        purchase.payment_id = pid
        purchase.save(update_fields=["quantity", "amount", "payment_id"])

    # 8) Overpayment anomaly
    remainder = amt - (price * final)
    if remainder > 0:
        TicketAnomaly.objects.create(
            lottery=lot,
            user=user,
            character=char,
            reason=f"Overpayment of {remainder} ISK",
            payment_date=date,
            amount=remainder,
            payment_id=pid,
        )

    # 9) Mark payment processed
    ProcessedPayment.objects.create(
        payment_id=pid,
        character=char,
        user=user,
        amount=amt,
        payed_at=date,
    )

    # 10) Recompute net pot
    lot.update_total_pot()


@shared_task(bind=True)
def process_payment_task(self, entry_id):
    """
    Asynchronous wrapper for process_payment.

    This task loads a wallet entry and processes it within a database transaction
    to ensure data consistency.

    Args:
        self: Task instance (Celery standard)
        entry_id: ID of the CorporationWalletJournalEntry to process
    """
    Journal = apps.get_model("corptools", "CorporationWalletJournalEntry")
    with transaction.atomic():
        entry = Journal.objects.select_for_update().get(entry_id=entry_id)
        process_payment(entry)


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Periodically scan for unprocessed payments.

    This task searches for any wallet entries containing the word 'lottery'
    that haven't been processed yet, then creates a group of tasks to process
    each payment individually.
    """
    logger.info("Running check_purchased_tickets")
    Journal = apps.get_model("corptools", "CorporationWalletJournalEntry")
    Processed = apps.get_model("fortunaisk", "ProcessedPayment")
    processed_ids = set(Processed.objects.values_list("payment_id", flat=True))
    pending = Journal.objects.filter(reason__icontains="lottery", amount__gt=0).exclude(
        entry_id__in=processed_ids
    )
    if pending:
        group(*(process_payment_task.s(p.entry_id) for p in pending)).apply_async()


@shared_task(bind=True, max_retries=5)
def check_lottery_status(self):
    """
    Manage lottery status transitions.

    This task:
    1) Transitions ACTIVE→PENDING when end_date ≤ now
    2) Waits 5 minutes after the audit task has run
    3) Transitions PENDING→COMPLETED: draws winners, distributes prizes, creates Winner records

    Uses a cache lock to prevent concurrent execution.
    """
    lock = "check_lottery_status_lock"
    if not cache.add(lock, "1", timeout=300):
        return
    try:
        now = timezone.now()
        LotteryModel = apps.get_model("fortunaisk", "Lottery")
        Journal = apps.get_model("corptools", "CorporationWalletJournalEntry")
        Processed = apps.get_model("fortunaisk", "ProcessedPayment")
        Purchase = apps.get_model("fortunaisk", "TicketPurchase")
        Winner = apps.get_model("fortunaisk", "Winner")
        # fortunaisk
        from fortunaisk.models.winner_distribution import WinnerDistribution

        # 1) ACTIVE→PENDING
        for lot in LotteryModel.objects.filter(status="active", end_date__lte=now):
            lot.status = "pending"
            lot.save(update_fields=["status"])
            logger.info(f"{lot.lottery_reference} → pending")

        # 2) Wait for audit + 5'
        try:
            audit = PeriodicTask.objects.get(name="Corporation Audit Update")
            last_run = audit.last_run_at
        except PeriodicTask.DoesNotExist:
            logger.warning("Audit task not found, delaying closure.")
            return
        if not last_run or now < last_run + timedelta(minutes=5):
            return

        # 3) PENDING→COMPLETED
        pendings = LotteryModel.objects.filter(status="pending", end_date__lte=last_run)
        for lot in pendings:
            unpaid = Journal.objects.filter(
                reason__iexact=lot.lottery_reference.lower(),
                amount__gt=0,
                date__lte=last_run,
            ).exclude(
                entry_id__in=Processed.objects.values_list("payment_id", flat=True)
            )
            if unpaid.exists():
                logger.info(
                    f"Unprocessed payments for {lot.lottery_reference}, retry later."
                )
                continue

            raw_winners = (
                lot.select_winners()
                if Purchase.objects.filter(lottery=lot).exists()
                else []
            )
            lot.update_total_pot()
            pot_net = lot.total_pot

            # build percentages
            dist_qs = WinnerDistribution.objects.filter(
                lottery_reference=lot.lottery_reference
            ).order_by("winner_rank")
            percentages = [wd.winner_prize_distribution for wd in dist_qs]
            n_winners = len(raw_winners)
            if len(percentages) != n_winners and n_winners > 0:
                base = (Decimal("100") / n_winners).quantize(Decimal("0.01"))
                percentages = [base] * n_winners
                percentages[-1] = Decimal("100") - base * (n_winners - 1)

            # compute allocations
            allocations, cumu = [], Decimal("0")
            for idx, pct in enumerate(percentages):
                share = (pot_net * pct / Decimal("100")).quantize(Decimal("0.01"))
                if idx == n_winners - 1:
                    share = pot_net - cumu
                else:
                    cumu += share
                allocations.append(share)

            # create winners
            ts = timezone.now()
            for purchase, prize in zip(raw_winners, allocations):
                Winner.objects.create(
                    ticket=purchase,
                    character=getattr(purchase, "character", None),
                    prize_amount=prize,
                    won_at=ts,
                )
            lot.status = "completed"
            lot.save(update_fields=["status"])
            logger.info(f"{lot.lottery_reference} → completed")
    finally:
        cache.delete(lock)


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_id: int):
    """
    Create a new lottery from an AutoLottery configuration.

    This task loads an AutoLottery by ID and uses it to create a new
    standard lottery if the AutoLottery is active.

    Args:
        self: Task instance (Celery standard)
        auto_id: ID of the AutoLottery configuration to use

    Returns:
        int: ID of the created lottery, or None if creation failed
    """
    Auto = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto = Auto.objects.get(id=auto_id, is_active=True)
        new = auto.create_lottery()
        logger.info(f"Created {new.lottery_reference} from AutoLottery {auto_id}")
        return new.id
    except Exception as e:
        logger.error(f"Error creating lottery from auto {auto_id}: {e}", exc_info=True)
        return None


@shared_task(bind=True)
def finalize_lottery(self, lot_id: int):
    """
    Manually finalize a lottery.

    This task directly completes a lottery by selecting winners and marking
    the lottery as completed, bypassing the normal workflow.

    Args:
        self: Task instance (Celery standard)
        lot_id: ID of the lottery to finalize
    """
    LotteryModel = apps.get_model("fortunaisk", "Lottery")
    lot = LotteryModel.objects.filter(id=lot_id).first()
    if not lot or lot.status not in ("active", "pending"):
        return
    winners = lot.select_winners()
    lot.status = "completed"
    lot.save(update_fields=["status"])
    logger.info(f"Finalized {lot.lottery_reference}, {len(winners)} winners.")


@shared_task(bind=True)
def send_lottery_closure_reminders(self):
    """
    Send reminders for lotteries closing soon.

    This task runs at the top of each hour and sends reminders for any
    lotteries that will be closing in the next 24-25 hours (one reminder per lottery).
    """
    now = timezone.now()
    Lottery = apps.get_model("fortunaisk", "Lottery")
    
    # Lotteries qui se terminent entre 24h et 25h à partir de maintenant
    upcoming = Lottery.objects.filter(
        status="active", 
        end_date__gte=now + timedelta(hours=24),
        end_date__lt=now + timedelta(hours=25)
    ).order_by("end_date")

    if not upcoming.exists():
        return

    admins = (
        apps.get_model("auth", "User")
        .objects.filter(groups__permissions__codename="can_admin_app")
        .distinct()
    )

    for lot in upcoming:
        # Get current pot for promotion
        current_pot = lot.total_pot or 0
        ticket_price = lot.ticket_price

        # Create more engaging embed
        embed = build_embed(
            title="🚨 LAST CHANCE: Lottery Ending in 24 Hours! 🚨",
            description=(
                f"**{lot.lottery_reference}** is closing in just 24 hours! ⏳\n\n"
                f"🏆 **Current Pot: {current_pot:,.2f} ISK**\n"
                f"💰 Ticket Price: {ticket_price:,.2f} ISK\n"
                f"⏰ Closes: {lot.end_date.strftime('%Y-%m-%d %H:%M')}\n\n"
                f"**💥 FINAL COUNTDOWN - DON'T MISS OUT! 💥**\n"
                f"This is your LAST CHANCE to grab tickets and win big!\n\n"
                f"💸 **How to participate:**\n"
                f"Send ISK to **{lot.payment_receiver}** with `{lot.lottery_reference}` in the payment reason."
            ),
            level="warning",
        )

        notify_discord_or_fallback(
            users=admins,
            event="reminder_24h_before_closure",
            embed=embed,
            private=False,
        )
        logger.info("Sent 24h reminder for %s", lot.lottery_reference)


def setup_periodic_tasks():
    """
    Create/update periodic tasks in cron mode:

    This function configures the following scheduled tasks:
    - check_purchased_tickets: runs every 30 minutes
    - check_lottery_status: runs every 2 minutes
    - send_lottery_closure_reminders: runs at the top of every hour
    """
    # 1) every 30 min
    sched30, _ = CrontabSchedule.objects.get_or_create(
        minute="*/30", hour="*", day_of_month="*", month_of_year="*", day_of_week="*"
    )
    PeriodicTask.objects.update_or_create(
        name="check_purchased_tickets",
        defaults={
            "task": "fortunaisk.tasks.check_purchased_tickets",
            "crontab": sched30,
            "interval": None,
            "args": json.dumps([]),
            "enabled": True,
        },
    )

    # 2) every 2 min
    sched2, _ = CrontabSchedule.objects.get_or_create(
        minute="*/2", hour="*", day_of_month="*", month_of_year="*", day_of_week="*"
    )
    PeriodicTask.objects.update_or_create(
        name="check_lottery_status",
        defaults={
            "task": "fortunaisk.tasks.check_lottery_status",
            "crontab": sched2,
            "interval": None,
            "args": json.dumps([]),
            "enabled": True,
        },
    )

    # 3) every hour on the hour
    sched1h, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour="*", day_of_month="*", month_of_year="*", day_of_week="*"
    )
    PeriodicTask.objects.update_or_create(
        name="send_lottery_closure_reminders",
        defaults={
            "task": "fortunaisk.tasks.send_lottery_closure_reminders",
            "crontab": sched1h,
            "interval": None,
            "args": json.dumps([]),
            "enabled": True,
        },
    )

    logger.info("FortunaIsk cron tasks registered.")
