# fortunaisk/tasks.py

# Standard Library
import json
import logging

# Third Party
from celery import shared_task

# Django
from django.apps import apps
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

# fortunaisk
from fortunaisk.notifications import send_alliance_auth_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Checks payments containing "lottery" in the reason,
    creates corresponding TicketPurchase entries, and marks payments as processed.
    """
    logger.info("Starting 'check_purchased_tickets' task.")
    try:
        # Retrieve necessary models with correct import paths
        CorporationWalletJournalEntryModel = apps.get_model(
            "corptools", "CorporationWalletJournalEntry"
        )
        ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")
        TicketAnomaly = apps.get_model("fortunaisk", "TicketAnomaly")
        Lottery = apps.get_model("fortunaisk", "Lottery")
        EveCharacter = apps.get_model("eveonline", "EveCharacter")
        CharacterOwnership = apps.get_model("authentication", "CharacterOwnership")
        UserProfile = apps.get_model("authentication", "UserProfile")
        TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")

        # Retrieve IDs of already processed payments
        processed_payment_ids = list(
            ProcessedPayment.objects.values_list("payment_id", flat=True)
        )

        # Filter payments containing "lottery" and not yet processed
        pending_payments = CorporationWalletJournalEntryModel.objects.filter(
            reason__icontains="lottery"
        ).exclude(entry_id__in=processed_payment_ids)

        logger.debug(f"Number of pending payments: {pending_payments.count()}")

        for payment in pending_payments:
            with transaction.atomic():
                try:
                    logger.debug(f"Processing payment ID: {payment.id}")

                    # Lock the payment row to prevent concurrent processing
                    payment_locked = CorporationWalletJournalEntryModel.objects.select_for_update().get(
                        id=payment.id
                    )

                    # Re-check if the payment has already been processed
                    if ProcessedPayment.objects.filter(
                        payment_id=payment_locked.entry_id
                    ).exists():
                        logger.debug(
                            f"Payment ID {payment_locked.id} has already been processed. Skipping."
                        )
                        continue

                    # Step 1: Extract necessary information
                    lottery_reference = payment_locked.reason.strip().lower()
                    amount = payment_locked.amount
                    payment_id = payment_locked.entry_id
                    payment_date = payment_locked.date

                    logger.debug(
                        f"Extracted payment ID {payment_id}: lottery_reference='{lottery_reference}', amount={amount}"
                    )

                    # Step 2: Find the corresponding active lottery
                    try:
                        lottery = Lottery.objects.select_for_update().get(
                            lottery_reference=lottery_reference, status="active"
                        )
                        logger.debug(
                            f"Found lottery '{lottery_reference}': ID {lottery.id}"
                        )
                    except Lottery.DoesNotExist:
                        logger.warning(
                            f"No active lottery found for reference '{lottery_reference}'. Payment ID {payment_id} ignored."
                        )
                        # Record an anomaly without user and character
                        TicketAnomaly.objects.create(
                            lottery=None,
                            reason=f"No active lottery found for reference '{lottery_reference}'.",
                            payment_date=payment_date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Mark the payment as processed
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Payment ID {payment_id} marked as processed due to anomaly."
                        )
                        continue

                    # **Nouveau : Step 3 - Find the user and main character BEFORE Date and Amount Checks**
                    try:
                        logger.debug(
                            f"Looking up EveCharacter with character_id={payment_locked.first_party_name_id}."
                        )
                        # Find EveCharacter linked to the payment
                        eve_character = EveCharacter.objects.get(
                            character_id=payment_locked.first_party_name_id
                        )
                        logger.debug(
                            f"EveCharacter found: ID {eve_character.id} for payment ID {payment_id}."
                        )

                        # Find CharacterOwnership via ForeignKey relationship
                        character_ownership = CharacterOwnership.objects.get(
                            character__character_id=eve_character.character_id
                        )
                        logger.debug(
                            f"CharacterOwnership found: user_id={character_ownership.user_id} for character ID {eve_character.character_id}."
                        )

                        # Find UserProfile from CharacterOwnership
                        user_profile = UserProfile.objects.get(
                            user_id=character_ownership.user_id
                        )
                        logger.debug(
                            f"UserProfile found: user_id={user_profile.user_id} associated with CharacterOwnership."
                        )

                        # Retrieve the main character
                        main_character_id = user_profile.main_character_id
                        main_eve_character = EveCharacter.objects.get(
                            id=main_character_id
                        )
                        main_character_name = main_eve_character.character_name

                        user = user_profile.user
                        logger.debug(
                            f"Main character retrieved: ID {main_character_id}, Name '{main_character_name}' for user '{user.username}'."
                        )

                    except EveCharacter.DoesNotExist:
                        logger.warning(
                            f"No EveCharacter found for first_party_name_id: {payment_locked.first_party_name_id}."
                        )
                        # Record an anomaly without user and character
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            reason="EveCharacter does not exist",
                            payment_date=payment_date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Mark the payment as processed
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Payment ID {payment_id} marked as processed due to missing EveCharacter."
                        )
                        continue
                    except CharacterOwnership.DoesNotExist:
                        logger.warning(
                            f"No CharacterOwnership found for character_id: {eve_character.character_id}."
                        )
                        # Record an anomaly without user
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=None,
                            character=eve_character,
                            reason="CharacterOwnership does not exist",
                            payment_date=payment_date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Mark the payment as processed
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Payment ID {payment_id} marked as processed due to missing CharacterOwnership."
                        )
                        continue
                    except UserProfile.DoesNotExist:
                        logger.warning(
                            f"No UserProfile found for user_id: {character_ownership.user_id}."
                        )
                        # Record an anomaly without user
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=None,
                            character=eve_character,
                            reason="UserProfile does not exist",
                            payment_date=payment_date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Mark the payment as processed
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Payment ID {payment_id} marked as processed due to missing UserProfile."
                        )
                        continue

                    # Step 3: Check if the payment date is within the lottery period
                    if not (lottery.start_date <= payment_date <= lottery.end_date):
                        logger.warning(
                            f"Payment date {payment_date} is outside the lottery period "
                            f"({lottery.start_date} - {lottery.end_date}) for lottery '{lottery.lottery_reference}'."
                        )
                        # Record an anomaly with user and character
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=user,
                            character=eve_character,
                            reason=f"Payment date {payment_date} is outside the lottery period.",
                            payment_date=payment_date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Mark the payment as processed
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Payment ID {payment_id} marked as processed due to date mismatch."
                        )
                        continue

                    # Step 4: Check if the payment amount matches the lottery's ticket price
                    if amount != lottery.ticket_price:
                        logger.warning(
                            f"Payment amount {amount} ISK does not match the ticket price "
                            f"{lottery.ticket_price} ISK for lottery '{lottery.lottery_reference}'."
                        )
                        # Record an anomaly with user and character
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=user,
                            character=eve_character,
                            reason=f"Payment amount {amount} ISK does not match the ticket price {lottery.ticket_price} ISK.",
                            payment_date=payment_date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Mark the payment as processed
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Payment ID {payment_id} marked as processed due to incorrect amount."
                        )
                        continue

                    # Step 5: Check the number of tickets the user has (grouped by main character)
                    lottery_max_tickets = lottery.max_tickets_per_user
                    if lottery_max_tickets:
                        user_ticket_count = TicketPurchase.objects.filter(
                            lottery=lottery,
                            user=user,
                            character__id=user_profile.main_character_id,
                        ).count()
                        logger.debug(
                            f"User '{user.username}' currently has {user_ticket_count} tickets "
                            f"for lottery '{lottery.lottery_reference}' (Main Character: {main_character_name})."
                        )
                        if user_ticket_count >= lottery_max_tickets:
                            logger.warning(
                                f"User '{user.username}' has reached the maximum number of tickets "
                                f"({lottery_max_tickets}) for lottery '{lottery.lottery_reference}'."
                            )
                            # Record an anomaly with user and character
                            TicketAnomaly.objects.create(
                                lottery=lottery,
                                user=user,
                                character=eve_character,
                                reason="Max tickets per user exceeded",
                                payment_date=payment_date,
                                amount=amount,
                                payment_id=payment_id,
                            )
                            # Mark the payment as processed
                            ProcessedPayment.objects.create(payment_id=payment_id)
                            logger.info(
                                f"Payment ID {payment_id} marked as processed due to ticket limit exceeded."
                            )
                            # Notify the user of the anomaly
                            send_alliance_auth_notification(
                                user=user,
                                title="⚠️ **Ticket Limit Reached** ⚠️",
                                message=(
                                    f"Hello {user.username},\n\n"
                                    f"You have reached the maximum number of tickets ({lottery_max_tickets}) pour la loterie **'{lottery.lottery_reference}'**. 🚫 "
                                    f"Your payment of **{amount} ISK** 💸 could not be processed."
                                ),
                                level="warning",
                            )
                            continue

                    # Step 6: Create a TicketPurchase entry
                    ticket_purchase = TicketPurchase.objects.create(
                        lottery=lottery,
                        user=user,
                        character=eve_character,  # Directly associate the character
                        amount=amount,
                        payment_id=str(payment_id),
                        status="processed",  # Set to processed directly
                    )

                    logger.info(
                        f"TicketPurchase ID {ticket_purchase.id} created for user '{user.username}' "
                        f"in lottery '{lottery.lottery_reference}'."
                    )

                    # Update lottery's total_pot
                    lottery.total_pot = (
                        lottery.ticket_purchases.aggregate(total=Sum("amount"))["total"]
                        or 0
                    )
                    lottery.save(update_fields=["total_pot"])

                    logger.debug(
                        f"Updated lottery '{lottery.lottery_reference}': total_pot updated."
                    )

                    # Step 7: Mark the payment as processed by creating a ProcessedPayment entry
                    ProcessedPayment.objects.create(payment_id=payment_id)
                    logger.info(
                        f"Payment ID {payment_id} marked as processed successfully."
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing payment ID {payment_id}: {e}",
                        exc_info=True,
                    )
                    # Optionally, retry the task
                    try:
                        self.retry(exc=e, countdown=60, max_retries=3)
                        logger.debug(
                            f"Requesting retry of the task for payment ID {payment_id}."
                        )
                    except self.MaxRetriesExceededError:
                        logger.error(
                            f"Maximum retry attempts exceeded for payment ID {payment_id}."
                        )
    except Exception as outer_e:
        logger.critical(
            f"General error in 'check_purchased_tickets' task: {outer_e}",
            exc_info=True,
        )
        # Optionally, notify admins of failure


@shared_task(bind=True)
def check_lottery_status(self):
    """
    Checks the status of lotteries every 15 minutes and closes completed lotteries.
    Before closing, rechecks the purchased tickets.
    """
    logger.info("Starting 'check_lottery_status' task.")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        now = timezone.now()
        active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
        logger.debug(f"Number of active lotteries to close: {active_lotteries.count()}")

        for lottery in active_lotteries:
            try:
                logger.debug(
                    f"Starting closure of lottery '{lottery.lottery_reference}' (ID {lottery.id})."
                )
                # Recheck purchased tickets if necessary
                logger.debug(
                    f"Rechecking tickets for lottery '{lottery.lottery_reference}'."
                )

                # Ici, ajoutez des vérifications spécifiques des tickets si nécessaire
                # Par exemple, vérifier si le montant correspond à un ticket valide

                # Fermer la loterie
                lottery.complete_lottery()
                logger.info(
                    f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) successfully closed."
                )

            except Exception as e:
                logger.error(
                    f"Error closing lottery '{lottery.lottery_reference}' (ID {lottery.id}): {e}",
                    exc_info=True,
                )
                # Optionally, notify admins of failure

        logger.info("'check_lottery_status' task execution completed successfully.")
    except Exception as e:
        logger.critical(f"Error in 'check_lottery_status' task: {e}", exc_info=True)
        # Optionally, notify admins of failure


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_lottery_id: int):
    """
    Creates a Lottery based on a specific AutoLottery.
    """
    logger.info(
        f"Starting 'create_lottery_from_auto_lottery' task for AutoLottery ID {auto_lottery_id}."
    )
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        logger.debug(
            f"Found AutoLottery: ID {auto_lottery.id}, name='{auto_lottery.name}'. Creating associated Lottery."
        )
        new_lottery = auto_lottery.create_lottery()
        logger.info(
            f"Lottery '{new_lottery.lottery_reference}' (ID {new_lottery.id}) created from AutoLottery '{auto_lottery.name}' (ID {auto_lottery.id})."
        )
        return new_lottery.id
    except AutoLottery.DoesNotExist:
        logger.error(
            f"AutoLottery with ID {auto_lottery_id} does not exist or is inactive."
        )
    except Exception as e:
        logger.error(
            f"Error creating Lottery from AutoLottery ID {auto_lottery_id}: {e}",
            exc_info=True,
        )
    return None


@shared_task(bind=True)
def finalize_lottery(self, lottery_id: int):
    """
    Finalizes a Lottery once it has ended.
    Selects winners, updates status, and sends notifications.
    """
    logger.info(f"Starting 'finalize_lottery' task for Lottery ID {lottery_id}.")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        logger.debug(
            f"Found Lottery: '{lottery.lottery_reference}' (ID {lottery.id}), current status: '{lottery.status}'."
        )
        if lottery.status != "active":
            logger.info(
                f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) is not active. Current status: '{lottery.status}'. No action taken."
            )
            return

        # Select winners
        winners = lottery.select_winners()
        logger.info(
            f"{len(winners)} winner(s) selected for Lottery '{lottery.lottery_reference}' (ID {lottery.id})."
        )

        if not winners:
            logger.warning(
                f"No winners selected for lottery '{lottery.lottery_reference}' (ID {lottery.id})."
            )
            lottery.status = "completed"
            lottery.save(update_fields=["status"])
            logger.info(
                f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) marked as 'completed' without winners."
            )
            return

        # Update lottery status
        lottery.status = "completed"
        lottery.save(update_fields=["status"])
        logger.debug(
            f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) status updated to 'completed'."
        )

        # Notifications are handled via signals when Winners are created

        logger.info(
            f"Finalization of Lottery '{lottery.lottery_reference}' (ID {lottery.id}) completed successfully."
        )
    except Lottery.DoesNotExist:
        logger.error(f"Lottery with ID {lottery_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Error finalizing Lottery ID {lottery_id}: {e}",
            exc_info=True,
        )
        # Optionally, retry the task
        try:
            self.retry(exc=e, countdown=60, max_retries=3)
            logger.debug(
                f"Retrying 'finalize_lottery' task for Lottery ID {lottery_id}."
            )
        except self.MaxRetriesExceededError:
            logger.error(
                f"Maximum retry attempts exceeded for 'finalize_lottery' task of Lottery ID {lottery_id}."
            )


def setup_periodic_tasks():
    """
    Configure global periodic tasks for FortunaIsk.
    """
    logger.info("Configuring global periodic tasks for FortunaIsk.")
    try:
        # Retrieve necessary models
        IntervalScheduleModel = apps.get_model("django_celery_beat", "IntervalSchedule")
        PeriodicTaskModel = apps.get_model("django_celery_beat", "PeriodicTask")

        # Check if 'check_purchased_tickets' task already exists
        if not PeriodicTaskModel.objects.filter(
            name="check_purchased_tickets"
        ).exists():
            # check_purchased_tickets => every 5 minutes
            schedule_check_tickets, created = (
                IntervalScheduleModel.objects.get_or_create(
                    every=5,
                    period=IntervalScheduleModel.MINUTES,
                )
            )
            PeriodicTaskModel.objects.create(
                name="check_purchased_tickets",
                task="fortunaisk.tasks.check_purchased_tickets",
                interval=schedule_check_tickets,
                args=json.dumps([]),
            )
            if created:
                logger.debug("IntervalSchedule created for 'check_purchased_tickets'.")
            logger.info("Periodic task 'check_purchased_tickets' created.")

        else:
            logger.debug("Periodic task 'check_purchased_tickets' already exists.")

        # Check if 'check_lottery_status' task already exists
        if not PeriodicTaskModel.objects.filter(name="check_lottery_status").exists():
            # check_lottery_status => every 15 minutes
            schedule_check_lottery, created = (
                IntervalScheduleModel.objects.get_or_create(
                    every=15,
                    period=IntervalScheduleModel.MINUTES,
                )
            )
            PeriodicTaskModel.objects.create(
                name="check_lottery_status",
                task="fortunaisk.tasks.check_lottery_status",
                interval=schedule_check_lottery,
                args=json.dumps([]),
            )
            if created:
                logger.debug("IntervalSchedule created for 'check_lottery_status'.")
            logger.info("Periodic task 'check_lottery_status' created.")

        else:
            logger.debug("Periodic task 'check_lottery_status' already exists.")

        logger.info(
            "Global periodic task configuration for FortunaIsk completed successfully."
        )
    except Exception as e:
        logger.critical(
            f"Error configuring periodic tasks: {e}",
            exc_info=True,
        )
        # Optionally, notify admins of failure
