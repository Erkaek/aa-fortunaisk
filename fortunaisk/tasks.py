import json
import logging
import math
import time
import random
from decimal import Decimal
from datetime import timedelta

from celery import shared_task, group, current_app
from django.apps import apps
from django.core.cache import cache
from django.db import transaction, models
from django.db.models import Sum, Max
from django.utils import timezone

# Notifications
from fortunaisk.notifications import send_alliance_auth_notification, send_discord_notification

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
    """
    # Retrieve necessary models.
    CorpJournal = apps.get_model("corptools", "CorporationWalletJournalEntry")
    ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")
    TicketAnomaly = apps.get_model("fortunaisk", "TicketAnomaly")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    EveCharacter = apps.get_model("eveonline", "EveCharacter")
    CharacterOwnership = apps.get_model("authentication", "CharacterOwnership")
    UserProfile = apps.get_model("authentication", "UserProfile")
    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")

    payment_id = payment_locked.entry_id

    # Skip if already processed.
    if ProcessedPayment.objects.filter(payment_id=payment_id).exists():
        logger.debug(f"Payment ID {payment_id} already processed. Skipping.")
        return

    try:
        # Step 1: Retrieve user and character information.
        logger.debug(f"Looking up EveCharacter with character_id={payment_locked.first_party_name_id}.")
        eve_character = EveCharacter.objects.get(character_id=payment_locked.first_party_name_id)
        logger.debug(f"EveCharacter found: ID {eve_character.id} for payment ID {payment_id}.")

        character_ownership = CharacterOwnership.objects.get(character__character_id=eve_character.character_id)
        logger.debug(f"CharacterOwnership found for character ID {eve_character.character_id}.")

        user_profile = UserProfile.objects.get(user_id=character_ownership.user_id)
        logger.debug(f"UserProfile found for user_id {user_profile.user_id}.")

        main_character_id = user_profile.main_character_id
        main_eve_character = EveCharacter.objects.get(id=main_character_id)
        main_character_name = main_eve_character.character_name

        user = user_profile.user
        logger.debug(f"Main character retrieved: ID {main_character_id}, Name '{main_character_name}' for user '{user.username}'.")
    except EveCharacter.DoesNotExist:
        logger.warning(f"No EveCharacter found for first_party_name_id: {payment_locked.first_party_name_id}.")
        TicketAnomaly.objects.create(
            lottery=None, user=None, character=None,
            reason="EveCharacter does not exist",
            payment_date=payment_locked.date,
            amount=payment_locked.amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        return
    except CharacterOwnership.DoesNotExist:
        logger.warning(f"No CharacterOwnership found for character_id: {eve_character.character_id}.")
        TicketAnomaly.objects.create(
            lottery=None, user=None, character=eve_character,
            reason="CharacterOwnership does not exist",
            payment_date=payment_locked.date,
            amount=payment_locked.amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        return
    except UserProfile.DoesNotExist:
        logger.warning(f"No UserProfile found for user_id: {character_ownership.user_id}.")
        TicketAnomaly.objects.create(
            lottery=None, user=None, character=eve_character,
            reason="UserProfile does not exist",
            payment_date=payment_locked.date,
            amount=payment_locked.amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        return

    # Step 2: Extract lottery reference.
    lottery_reference = payment_locked.reason.strip().lower()
    payment_date = payment_locked.date
    payment_amount = payment_locked.amount
    logger.debug(f"Payment ID {payment_id}: lottery_reference='{lottery_reference}', amount={payment_amount}")

    # Step 3: Retrieve the active lottery.
    try:
        lottery = Lottery.objects.select_for_update().get(
            lottery_reference=lottery_reference,
            status__in=["active", "pending"]
        )
        logger.debug(f"Found lottery '{lottery_reference}': ID {lottery.id}")
    except Lottery.DoesNotExist:
        logger.warning(f"No active lottery found for reference '{lottery_reference}'. Payment ID {payment_id} ignored.")
        TicketAnomaly.objects.create(
            lottery=None, user=user, character=eve_character,
            reason=f"No active lottery found for reference '{lottery_reference}'.",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        return

    # Step 4: Verify that the payment date is within the lottery period.
    if not (lottery.start_date <= payment_date <= lottery.end_date):
        logger.warning(f"Payment date {payment_date} is outside the lottery period ({lottery.start_date} - {lottery.end_date}) for lottery '{lottery.lottery_reference}'.")
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=eve_character,
            reason=f"Payment date {payment_date} is outside the lottery period.",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        return

    # Step 5: Calculate the maximum full tickets purchasable.
    ticket_price = lottery.ticket_price
    num_tickets_possible = math.floor(payment_amount / ticket_price)
    if num_tickets_possible < 1:
        logger.warning(f"Payment amount {payment_amount} ISK is insufficient for even one ticket at {ticket_price} ISK for lottery '{lottery.lottery_reference}'.")
        TicketAnomaly.objects.create(
            lottery=lottery, user=user, character=eve_character,
            reason=f"Insufficient payment amount for one ticket (ticket price: {ticket_price} ISK).",
            payment_date=payment_date, amount=payment_amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        return

    # Step 6: Adjust for maximum tickets per user.
    final_tickets = num_tickets_possible
    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
    current_tickets = TicketPurchase.objects.filter(
        lottery=lottery,
        user=user,
        character__id=user_profile.main_character_id,
    ).aggregate(total=models.Sum("quantity"))["total"] or 0
    allowed_tickets = lottery.max_tickets_per_user - current_tickets if lottery.max_tickets_per_user else num_tickets_possible
    logger.debug(f"User '{user.username}' currently has {current_tickets} tickets for lottery '{lottery.lottery_reference}'. Allowed additional tickets: {allowed_tickets}.")
    if lottery.max_tickets_per_user and allowed_tickets < 1:
        logger.warning(f"User '{user.username}' has reached the maximum number of tickets ({lottery.max_tickets_per_user}) for lottery '{lottery.lottery_reference}'.")
        TicketAnomaly.objects.create(
            lottery=lottery,
            user=user,
            character=eve_character,
            reason="Max tickets per user exceeded",
            payment_date=payment_date,
            amount=payment_amount,
            payment_id=payment_id,
        )
        ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
        send_alliance_auth_notification(
            user=user,
            title="⚠️ Ticket Limit Reached",
            message=(f"Hello {user.username},\n\n"
                     f"You have reached the maximum number of tickets ({lottery.max_tickets_per_user}) for lottery '{lottery.lottery_reference}'. "
                     f"Your payment of {payment_amount} ISK could not be processed for additional tickets."),
            level="warning",
        )
        return
    final_tickets = min(num_tickets_possible, allowed_tickets)

    # Step 7: Create or update the TicketPurchase record.
    ticket_total_cost = final_tickets * ticket_price
    ticket_purchase, created = TicketPurchase.objects.get_or_create(
        lottery=lottery,
        user=user,
        character=eve_character,
        defaults={
            "amount": ticket_total_cost,
            "quantity": final_tickets,
            "status": "processed",
            "payment_id": payment_id,
        }
    )
    if not created:
        ticket_purchase.quantity += final_tickets
        ticket_purchase.amount += ticket_total_cost
        ticket_purchase.payment_id = payment_id  # Optionally update payment_id.
        ticket_purchase.save(update_fields=["quantity", "amount", "payment_id"])

    # Step 8: Compute the effective cost and determine any remainder.
    effective_cost = final_tickets * ticket_price
    remainder = payment_amount - effective_cost

    # Step 9: Record an anomaly if there's an overpayment.
    if remainder > 0:
        logger.warning(f"Payment ID {payment_id}: Overpayment detected. Remainder: {remainder} ISK not applied to ticket purchase.")
        TicketAnomaly.objects.create(
            lottery=lottery,
            user=user,
            character=eve_character,
            reason=f"Overpayment of {remainder:,.2f} ISK detected (expected {effective_cost:,.2f} ISK for {final_tickets:,} ticket(s)).",
            payment_date=payment_date,
            amount=remainder,
            payment_id=payment_id,
        )

    # Step 10: (Total pot update is deferred to the finalization phase.)

    # Step 11: Mark the payment as processed with current timestamp.
    ProcessedPayment.objects.create(payment_id=payment_id, processed_at=timezone.now())
    logger.info(f"Payment ID {payment_id} marked as processed successfully.")

    # Step 12: Send a detailed confirmation notification.
    notif_message = (
        f"Hello {user.username},\n\n"
        f"Your payment of {payment_amount} ISK has been processed for lottery '{lottery.lottery_reference}'.\n"
        f"You have purchased {final_tickets} ticket(s) at {ticket_price} ISK each, totaling {effective_cost} ISK.\n"
    )
    if remainder > 0:
        notif_message += f"An overpayment of {remainder} ISK was detected and has been recorded as an anomaly.\n"
    notif_message += "Good luck!"
    send_alliance_auth_notification(
        user=user,
        title="🍀 Ticket Purchase Confirmation",
        message=notif_message,
        level="info",
    )


@shared_task(bind=True)
def process_payment_task(self, payment_entry_id):
    """
    Asynchronously process a single payment identified by its entry_id.
    Retrieves the payment with a row-level lock and calls process_payment.
    """
    CorpJournal = apps.get_model("corptools", "CorporationWalletJournalEntry")
    try:
        with transaction.atomic():
            payment_locked = CorpJournal.objects.select_for_update().get(entry_id=payment_entry_id)
            process_payment(payment_locked)
    except Exception as e:
        logger.error(f"Error in process_payment_task for payment_id {payment_entry_id}: {e}", exc_info=True)
        raise e


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Checks for pending payments with a lottery reference and dispatches each for processing.
    Now waits for the completion of the group of tasks.
    """
    logger.info("Starting 'check_purchased_tickets' task.")
    try:
        CorpJournal = apps.get_model("corptools", "CorporationWalletJournalEntry")
        ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")

        processed_payment_ids = list(ProcessedPayment.objects.values_list("payment_id", flat=True))
        pending_payments = CorpJournal.objects.filter(
            reason__icontains="lottery",
            amount__gt=0,
        ).exclude(entry_id__in=processed_payment_ids)

        count = pending_payments.count()
        logger.debug(f"Number of pending payments: {count}")
        tasks = [process_payment_task.s(payment.entry_id) for payment in pending_payments]
        if tasks:
            result = group(tasks).apply_async()
            # Attendre que toutes les tâches aient terminé (timeout en secondes selon votre besoin)
            result.get(timeout=120)
    except Exception as outer_e:
        logger.critical(f"General error in 'check_purchased_tickets' task: {outer_e}", exc_info=True)


def wait_for_corp_audit_update():
    """
    Waits for the PeriodicTask "Corporation Audit Update" (from django_celery_beat)
    to have its last_run_at field updated. Once updated, waits an additional 10 seconds.
    If the maximum wait time is reached, proceeds anyway.
    """
    try:
        from django_celery_beat.models import PeriodicTask
        corp_task = PeriodicTask.objects.get(name="Corporation Audit Update")
        old_last_run = corp_task.last_run_at
        logger.info(f"Old last_run_at for 'Corporation Audit Update': {old_last_run}")
        total_wait = 0
        max_wait = 300  # Maximum of 5 minutes.
        while total_wait < max_wait:
            corp_task.refresh_from_db()
            if corp_task.last_run_at and corp_task.last_run_at != old_last_run:
                logger.info(f"New last_run_at detected: {corp_task.last_run_at}")
                time.sleep(10)  # Wait an additional 10 seconds.
                return
            time.sleep(10)
            total_wait += 10
        logger.warning("Timeout reached waiting for 'Corporation Audit Update'. Proceeding anyway.")
    except Exception as e:
        logger.warning(f"Could not retrieve 'Corporation Audit Update' periodic task: {e}. Proceeding immediately.")


@shared_task(bind=True, max_retries=5)
def check_lottery_status(self):
    """
    Every 2 minutes, checks for lotteries to be closed.
    For each lottery whose end date has passed:
      1. Sets its status to "pending".
      2. Waits for the Corporation Audit Update (plus 10 sec).
      3. Retrieves the latest processed payment date for this lottery.
         If none, uses the lottery end_date.
      4. If there are unprocessed payments beyond that date, launches check_purchased_tickets synchronously.
      5. Recalculates the total pot (via a fresh query) and finalizes the lottery.
    A cache lock prevents parallel executions.
    """
    lock_id = "check_lottery_status_lock"
    if not cache.add(lock_id, "true", timeout=300):
        logger.info("check_lottery_status already running. Exiting.")
        return

    try:
        Lottery = apps.get_model("fortunaisk", "Lottery")
        CorpJournal = apps.get_model("corptools", "CorporationWalletJournalEntry")
        ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")
        now = timezone.now()
        active_lotteries = Lottery.objects.filter(status__in=["active", "pending"], end_date__lte=now)
        logger.debug(f"Number of active lotteries to close: {active_lotteries.count()}")

        for lottery in active_lotteries:
            # 1. Passer la lottery en "pending"
            lottery.status = "pending"
            lottery.save(update_fields=["status"])
            logger.info(f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) set to 'pending'.")

            # 2. Attendre l'audit de la corp (plus 10 sec)
            wait_for_corp_audit_update()
            time.sleep(10)

            lottery_ref = lottery.lottery_reference.strip().lower()

            # 3. Déterminer la date du dernier paiement traité pour cette lottery.
            processed_payments_qs = CorpJournal.objects.filter(
                entry_id__in=ProcessedPayment.objects.values_list("payment_id", flat=True),
                reason__iexact=lottery_ref,
            )
            if processed_payments_qs.exists():
                last_processed_date = processed_payments_qs.order_by("-date").first().date
            else:
                last_processed_date = lottery.end_date

            # 4. Vérifier les paiements non traités postérieurs à last_processed_date.
            pending_payments = CorpJournal.objects.filter(
                reason__iexact=lottery_ref,
                amount__gt=0,
                date__gt=last_processed_date,
            ).exclude(entry_id__in=ProcessedPayment.objects.values_list("payment_id", flat=True))
            if pending_payments.exists():
                count = pending_payments.count()
                logger.info(f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) has {count} pending payment(s) after {last_processed_date}. Launching check_purchased_tickets synchronously.")
                # Lancer check_purchased_tickets et attendre son achèvement.
                check_purchased_tickets.apply().get(timeout=120)

            # 5. Recalculer le pot total en interrogeant TicketPurchase directement.
            TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
            total_data = TicketPurchase.objects.filter(lottery=lottery).aggregate(total=Sum("amount"))
            total = total_data.get("total") or 0
            lottery.total_pot = total
            lottery.save(update_fields=["total_pot"])
            logger.info(f"Updated total pot for lottery '{lottery.lottery_reference}' to {lottery.total_pot} ISK before finalization.")

            # 6. Finalisation : si le pot est > 0, tenter de sélectionner les gagnants.
            if lottery.total_pot == 0:
                logger.error(f"Total pot is 0 for lottery {lottery.lottery_reference}. Cannot select winners.")
            else:
                winners = lottery.select_winners()
                if winners:
                    logger.info(f"{len(winners)} winner(s) selected for Lottery '{lottery.lottery_reference}' (ID {lottery.id}).")
                else:
                    logger.warning(f"No winners selected for lottery '{lottery.lottery_reference}' (ID {lottery.id}).")
            lottery.status = "completed"
            lottery.save(update_fields=["status"])
            logger.info(f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) successfully closed.")
    finally:
        cache.delete(lock_id)


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_lottery_id: int):
    """
    Creates a Lottery based on a specific AutoLottery.
    """
    logger.info(f"Starting 'create_lottery_from_auto_lottery' task for AutoLottery ID {auto_lottery_id}.")
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        logger.debug(f"Found AutoLottery: ID {auto_lottery.id}, name='{auto_lottery.name}'. Creating associated Lottery.")
        new_lottery = auto_lottery.create_lottery()
        logger.info(f"Lottery '{new_lottery.lottery_reference}' (ID {new_lottery.id}) created from AutoLottery '{auto_lottery.name}' (ID {auto_lottery.id}).")
        return new_lottery.id
    except AutoLottery.DoesNotExist:
        logger.error(f"AutoLottery with ID {auto_lottery_id} does not exist or is inactive.")
    except Exception as e:
        logger.error(f"Error creating Lottery from AutoLottery ID {auto_lottery_id}: {e}", exc_info=True)
    return None


@shared_task(bind=True)
def finalize_lottery(self, lottery_id: int):
    """
    Finalizes a Lottery once it has ended.
    Selects winners, updates status, and sends notifications.
    Winner selection is based on a weighted random choice using the 'quantity' field of each TicketPurchase.
    """
    logger.info(f"Starting 'finalize_lottery' task for Lottery ID {lottery_id}.")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        logger.debug(f"Found Lottery: '{lottery.lottery_reference}' (ID {lottery.id}), current status: '{lottery.status}'.")
        if lottery.status not in ["active", "pending"]:
            logger.info(f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) is not active. Current status: '{lottery.status}'. No action taken.")
            return

        winners = lottery.select_winners()
        logger.info(f"{len(winners)} winner(s) selected for Lottery '{lottery.lottery_reference}' (ID {lottery.id}).")

        if not winners:
            logger.warning(f"No winners selected for lottery '{lottery.lottery_reference}' (ID {lottery.id}).")
            lottery.status = "completed"
            lottery.save(update_fields=["status"])
            logger.info(f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) marked as 'completed' without winners.")
            return

        lottery.status = "completed"
        lottery.save(update_fields=["status"])
        logger.debug(f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) status updated to 'completed'.")
        logger.info(f"Finalization of Lottery '{lottery.lottery_reference}' (ID {lottery.id}) completed successfully.")
    except Lottery.DoesNotExist:
        logger.error(f"Lottery with ID {lottery_id} does not exist.")
    except Exception as e:
        logger.error(f"Error finalizing Lottery ID {lottery_id}: {e}", exc_info=True)
        try:
            self.retry(exc=e, countdown=60, max_retries=3)
            logger.debug(f"Retrying 'finalize_lottery' task for Lottery ID {lottery_id}.")
        except self.MaxRetriesExceededError:
            logger.error(f"Maximum retry attempts exceeded for 'finalize_lottery' task of Lottery ID {lottery_id}.")


def setup_periodic_tasks():
    """
    Configures or updates global periodic tasks for FortunaIsk using update_or_create.
    """
    logger.info("Configuring global periodic tasks for FortunaIsk.")
    try:
        IntervalScheduleModel = apps.get_model("django_celery_beat", "IntervalSchedule")
        PeriodicTaskModel = apps.get_model("django_celery_beat", "PeriodicTask")

        # Set up or update the check_purchased_tickets task (every 30 minutes)
        schedule_check_tickets, _ = IntervalScheduleModel.objects.get_or_create(
            every=30,
            period=IntervalScheduleModel.MINUTES,
        )
        PeriodicTaskModel.objects.update_or_create(
            name="check_purchased_tickets",
            defaults={
                "task": "fortunaisk.tasks.check_purchased_tickets",
                "interval": schedule_check_tickets,
                "args": json.dumps([]),
            },
        )
        logger.info("Periodic task 'check_purchased_tickets' updated/created successfully.")

        # Set up or update the check_lottery_status task (every 2 minutes)
        schedule_check_lottery, _ = IntervalScheduleModel.objects.get_or_create(
            every=2,
            period=IntervalScheduleModel.MINUTES,
        )
        PeriodicTaskModel.objects.update_or_create(
            name="check_lottery_status",
            defaults={
                "task": "fortunaisk.tasks.check_lottery_status",
                "interval": schedule_check_lottery,
                "args": json.dumps([]),
            },
        )
        logger.info("Periodic task 'check_lottery_status' updated/created successfully.")

        logger.info("Global periodic task configuration for FortunaIsk completed successfully.")
    except Exception as e:
        logger.critical(f"Error configuring periodic tasks: {e}", exc_info=True)
