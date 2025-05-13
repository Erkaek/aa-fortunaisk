# fortunaisk/tasks.py

# Standard Library
import json
import logging
import math
from datetime import timedelta

# Third Party
from celery import group, shared_task
from django_celery_beat.models import PeriodicTask

# Django
from django.apps import apps
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

# fortunaisk
from fortunaisk.notifications import notify_discord_or_fallback

logger = logging.getLogger(__name__)


def process_payment(entry):
    """
    Process a single wallet payment into lottery tickets:
      1. Identify user & character.
      2. Find the active or pending lottery.
      3. Validate date within period.
      4. Compute full tickets purchasable.
      5. Enforce per-user ticket limit.
      6. Create/update TicketPurchase.
      7. Record anomalies (overpayment, invalid).
      8. Mark payment processed & notify user.
      9. Recalculate lottery total pot.
    """
    # Dynamically get models
    ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")
    TicketAnomaly = apps.get_model("fortunaisk", "TicketAnomaly")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    EveCharacter = apps.get_model("eveonline", "EveCharacter")
    CharacterOwnership = apps.get_model("authentication", "CharacterOwnership")
    UserProfile = apps.get_model("authentication", "UserProfile")
    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")

    pid = entry.entry_id
    date = entry.date
    amt = entry.amount
    ref = entry.reason.strip().lower()

    # Already processed?
    if ProcessedPayment.objects.filter(payment_id=pid).exists():
        logger.debug(f"Payment {pid} already processed, skipping.")
        return

    # 1) Get user/character
    try:
        char = EveCharacter.objects.get(character_id=entry.first_party_name_id)
        ownership = CharacterOwnership.objects.get(
            character__character_id=char.character_id
        )
        profile = UserProfile.objects.get(user_id=ownership.user_id)
        user = profile.user
    except Exception as e:
        reason = " | ".join(
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
                "Profile missing" if isinstance(e, UserProfile.DoesNotExist) else "",
            ]
        ).strip(" |")
        TicketAnomaly.objects.create(
            lottery=None,
            user=None,
            character=None,
            reason=reason or str(e),
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 2) Get lottery (active or pending)
    try:
        lot = Lottery.objects.select_for_update().get(
            lottery_reference=ref, status__in=["active", "pending"]
        )
    except Lottery.DoesNotExist:
        TicketAnomaly.objects.create(
            lottery=None,
            user=user,
            character=char,
            reason=f"No active/pending lottery '{ref}'",
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 3) Check date range
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
        ProcessedPayment.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 4) Compute ticket count
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
        ProcessedPayment.objects.create(payment_id=pid, processed_at=timezone.now())
        return

    # 5) Enforce per-user limit
    existing = (
        TicketPurchase.objects.filter(
            lottery=lot, user=user, character__id=profile.main_character_id
        ).aggregate(total=Sum("quantity"))["total"]
        or 0
    )
    count = math.floor(amt / price)

    if lot.unlimited:
        # En mode illimité on valide l'intégralité de la demande
        final = count
    else:
        # Sinon on respecte la limite max_tickets_per_user
        remaining = max(0, lot.max_tickets_per_user - existing)
        final = min(count, remaining)

    if final < 1:
        # Cas où on a atteint la limite (ou count était 0)
        TicketAnomaly.objects.create(
            lottery=lot,
            user=user,
            character=char,
            reason="Ticket limit exceeded",
            payment_date=date,
            amount=amt,
            payment_id=pid,
        )
        ProcessedPayment.objects.create(payment_id=pid, processed_at=timezone.now())
        notify_discord_or_fallback(
            user,
            title="⚠️ Ticket Limit Reached",
            message=(
                f"You have reached the ticket limit "
                f"({lot.max_tickets_per_user}) for lottery {lot.lottery_reference}."
            ),
            level="warning",
        )
        return

    # 6) Create or update purchase
    cost = final * price
    purchase, created = TicketPurchase.objects.get_or_create(
        lottery=lot,
        user=user,
        character=char,
        defaults={
            "quantity": final,
            "amount": cost,
            "status": "processed",
            "payment_id": pid,
            "payment_id": pid,
        },
    )
    if not created:
        purchase.quantity += final
        purchase.amount += cost
        purchase.payment_id = pid
        purchase.save(update_fields=["quantity", "amount", "payment_id"])

    # 7) Handle overpayment
    remainder = amt - cost
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

    # 8) Mark processed & notify
    apps.get_model("fortunaisk", "ProcessedPayment").objects.create(
        payment_id=pid, processed_at=timezone.now()
    )

    # 9) Update total pot
    total = (
        TicketPurchase.objects.filter(lottery=lot).aggregate(sum=Sum("amount"))["sum"]
        or 0
    )
    lot.total_pot = total
    lot.save(update_fields=["total_pot"])


@shared_task(bind=True)
def process_payment_task(self, entry_id):
    """
    Async wrapper to process a single payment entry.
    """
    Journal = apps.get_model("corptools", "CorporationWalletJournalEntry")
    with transaction.atomic():
        entry = Journal.objects.select_for_update().get(entry_id=entry_id)
        process_payment(entry)


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Periodic scan for new lottery payments and dispatch processing tasks.
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
    Close lotteries only after 'Corporation Audit Update' + 5-minute safety:
      1) ACTIVE→PENDING when expired
      2) wait for audit run after end_date
      3) wait 5-min grace, logging remaining time
      4) PENDING→COMPLETED, select winners
    """
    lock = "check_lottery_status_lock"
    if not cache.add(lock, "1", timeout=300):
        return
    try:
        now = timezone.now()
        Lottery = apps.get_model("fortunaisk", "Lottery")

        # 1) ACTIVE→PENDING
        for lot in Lottery.objects.filter(status="active", end_date__lte=now):
            lot.status = "pending"
            lot.save(update_fields=["status"])
            logger.info(f"{lot.lottery_reference} → pending")

        # 2) audit timestamp
        try:
            audit = PeriodicTask.objects.get(name="Corporation Audit Update")
            last_run = audit.last_run_at
        except PeriodicTask.DoesNotExist:
            logger.warning("Audit task not found, delaying closure.")
            return
        if not last_run:
            logger.info("Awaiting first audit run before closing lotteries.")
            return

        # check earliest pending lottery end_date
        pending = Lottery.objects.filter(status="pending")
        if not pending.exists():
            return
        end0 = pending.order_by("end_date").first().end_date

        # 3A) audit too early
        if last_run < end0:
            logger.info(f"Audit at {last_run} before end_date {end0}, delaying.")
            return
        # 3B) 5-min grace
        grace_end = last_run + timedelta(minutes=5)
        if now < grace_end:
            rem = str(grace_end - now).split(".")[0]
            logger.info(f"In grace until {grace_end} (remaining {rem}).")
            return

        # 4) COMPLETE
        Journal = apps.get_model("corptools", "CorporationWalletJournalEntry")
        Processed = apps.get_model("fortunaisk", "ProcessedPayment")
        Purchase = apps.get_model("fortunaisk", "TicketPurchase")

        for lot in pending.filter(end_date__lte=last_run):
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
                check_purchased_tickets.delay()
                continue

            total = (
                Purchase.objects.filter(lottery=lot).aggregate(sum=Sum("amount"))["sum"]
                or 0
            )
            winners = lot.select_winners() if total > 0 else []
            logger.info(f"{lot.lottery_reference}: {len(winners)} winner(s).")
            lot.total_pot = total
            lot.status = "completed"
            lot.save(update_fields=["total_pot", "status"])
            logger.info(f"{lot.lottery_reference} → completed")

    finally:
        cache.delete(lock)


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_id: int):
    """
    Generate a Lottery from an AutoLottery definition.
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
    Finalize a lottery (select winners) when invoked manually.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    lot = Lottery.objects.filter(id=lot_id).first()
    if not lot or lot.status not in ("active", "pending"):
        return
    winners = lot.select_winners()
    lot.status = "completed"
    lot.save(update_fields=["status"])
    logger.info(f"Finalized {lot.lottery_reference}, {len(winners)} winners.")


def setup_periodic_tasks():
    """
    Register global Celery Beat tasks:
      - check_purchased_tickets: every 30m
      - check_lottery_status: every 2m
    """
    logger.info("Configuring periodic tasks for FortunaIsk.")
    Interval = apps.get_model("django_celery_beat", "IntervalSchedule")
    Periodic = apps.get_model("django_celery_beat", "PeriodicTask")

    sched30, _ = Interval.objects.get_or_create(every=30, period=Interval.MINUTES)
    Periodic.objects.update_or_create(
        name="check_purchased_tickets",
        defaults={
            "task": "fortunaisk.tasks.check_purchased_tickets",
            "interval": sched30,
            "args": json.dumps([]),
            "enabled": True,
        },
    )

    sched2, _ = Interval.objects.get_or_create(every=2, period=Interval.MINUTES)
    Periodic.objects.update_or_create(
        name="check_lottery_status",
        defaults={
            "task": "fortunaisk.tasks.check_lottery_status",
            "interval": sched2,
            "args": json.dumps([]),
            "enabled": True,
        },
    )

    logger.info("Periodic tasks registered.")
