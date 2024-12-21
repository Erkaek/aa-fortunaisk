# fortunaisk/tasks.py

# Standard Library
import json
import logging
from datetime import timedelta
from random import shuffle

# Third Party
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .models import AutoLottery, Lottery, TicketAnomaly, TicketPurchase, Winner
from .notifications import send_discord_notification

logger = logging.getLogger(__name__)


def send_discord_dm(user, message):
    """
    Envoie un DM au utilisateur sur Discord.
    TODO: Implémenter la logique réelle d'envoi de DM si l'ID Discord de l'utilisateur est connu.
    """
    # Placeholder pour l'implémentation réelle.
    pass


@shared_task
def check_lotteries():
    """
    Vérifie toutes les loteries actives qui ont dépassé leur date de fin et sélectionne les gagnants.
    """
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
    for lottery in active_lotteries:
        select_winners_for_lottery(lottery)


def select_winners_for_lottery(lottery):
    """
    Sélectionne plusieurs gagnants pour la loterie donnée et distribue le pot.
    """
    participants = User.objects.filter(ticketpurchase__lottery=lottery).distinct()
    participant_count = participants.count()

    if participant_count == 0:
        lottery.status = "completed"
        lottery.participant_count = 0
        lottery.total_pot = 0
        lottery.save()
        send_discord_notification(
            message=f"Aucune participation pour la loterie {lottery.lottery_reference}. La loterie s'est terminée sans gagnants."
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
        for idx, ticket in enumerate(chosen_tickets):
            # Assurez-vous que la distribution est définie et correspond au nombre de gagnants
            if idx < len(distribution):
                percent = distribution[idx]
            else:
                percent = (
                    100 / winners_count
                )  # Répartir équitablement si distribution manquante

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
    send_discord_notification(
        message=f"La loterie {lottery.lottery_reference} s'est terminée ! {winners_count} gagnants ont été sélectionnés. Pot total : {pot} ISK."
    )


@shared_task
def create_lottery_from_auto(auto_lottery_id):
    """
    Crée une nouvelle loterie à partir d'une Auto Lottery.
    """
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id)

        # Créer la nouvelle loterie
        start_date = timezone.now()

        # Convertir la durée en timedelta basé sur l'unité
        if auto_lottery.duration_unit == "hours":
            delta = timedelta(hours=auto_lottery.duration_value)
        elif auto_lottery.duration_unit == "days":
            delta = timedelta(days=auto_lottery.duration_value)
        elif auto_lottery.duration_unit == "months":
            delta = timedelta(days=30 * auto_lottery.duration_value)  # Approximation
        else:
            logger.error(f"Unsupported duration_unit: {auto_lottery.duration_unit}")
            delta = timedelta(hours=auto_lottery.duration_value)  # default

        end_date = start_date + delta

        lottery = Lottery.objects.create(
            ticket_price=auto_lottery.ticket_price,
            start_date=start_date,
            end_date=end_date,
            payment_receiver=auto_lottery.payment_receiver,
            winner_count=auto_lottery.winner_count,
            winners_distribution_str=auto_lottery.winners_distribution_str,
            max_tickets_per_user=auto_lottery.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=auto_lottery.duration_value,
            duration_unit=auto_lottery.duration_unit,
        )

        logger.info(
            f"Created new Lottery '{lottery.lottery_reference}' from AutoLottery '{auto_lottery.name}' (ID: {auto_lottery_id})"
        )
        return lottery.id

    except AutoLottery.DoesNotExist:
        logger.error(f"Auto Lottery with ID {auto_lottery_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Error creating Lottery from AutoLottery {auto_lottery_id}: {str(e)}"
        )


@shared_task
def process_wallet_tickets():
    """
    Traite les entrées de portefeuille pour toutes les loteries actives.
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
            logger.info(f"No payments found for Lottery ID: {lottery.id}")
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
                anomaly_reason = "Payment date outside lottery period."

            try:
                character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = character.character_ownership
                if not ownership or not ownership.user:
                    if anomaly_reason is None:
                        anomaly_reason = "No primary user for the character."
                else:
                    user = ownership.user
                    user_ticket_count = TicketPurchase.objects.filter(
                        user=user, lottery=lottery
                    ).count()
                    if user_ticket_count >= lottery.max_tickets_per_user:
                        if anomaly_reason is None:
                            anomaly_reason = f"User '{user.username}' has exceeded the maximum number of tickets ({lottery.max_tickets_per_user})."
            except EveCharacter.DoesNotExist:
                if anomaly_reason is None:
                    anomaly_reason = (
                        f"Eve Character {payment.first_party_name_id} not found."
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
                        payment_id=payment.id,  # Enregistrer l'ID du paiement
                    )
                    logger.info(f"Ticket recorded for user '{user.username}'.")
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
                logger.error(
                    f"Integrity error while processing payment {payment.id}: {e}"
                )
            except Exception as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=character,
                    user=user,
                    reason=f"Unexpected error: {e}",
                    payment_date=payment.date,
                    amount=int(payment.amount),
                    payment_id=payment.id,
                )
                logger.exception(
                    f"Unexpected error while processing payment {payment.id}: {e}"
                )

    logger.info(f"{processed_entries} tickets processed for all active lotteries.")
    return f"{processed_entries} tickets processed for all active lotteries."


def setup_tasks():
    try:
        # Schedule for check_lotteries task (every 15 minutes)
        check_lotteries_schedule, created = IntervalSchedule.objects.get_or_create(
            every=15,
            period=IntervalSchedule.MINUTES,
        )
    except IntervalSchedule.MultipleObjectsReturned:
        check_lotteries_schedule = IntervalSchedule.objects.filter(
            every=15,
            period=IntervalSchedule.MINUTES,
        ).first()

    try:
        # Schedule for process_wallet_tickets task (every 5 minutes)
        process_wallet_tickets_schedule, created = (
            IntervalSchedule.objects.get_or_create(
                every=5,
                period=IntervalSchedule.MINUTES,
            )
        )
    except IntervalSchedule.MultipleObjectsReturned:
        process_wallet_tickets_schedule = IntervalSchedule.objects.filter(
            every=5,
            period=IntervalSchedule.MINUTES,
        ).first()

    PeriodicTask.objects.update_or_create(
        name="check_lotteries",
        defaults={
            "task": "fortunaisk.tasks.check_lotteries",
            "interval": check_lotteries_schedule,
            "args": json.dumps([]),
        },
    )

    PeriodicTask.objects.update_or_create(
        name="process_wallet_tickets",
        defaults={
            "task": "fortunaisk.tasks.process_wallet_tickets",
            "interval": process_wallet_tickets_schedule,
            "args": json.dumps([]),
        },
    )

    logger.info(
        "Periodic tasks for checking lotteries and processing wallet tickets have been set up."
    )


# Appeler la fonction setup_tasks pour configurer les tâches
setup_tasks()
