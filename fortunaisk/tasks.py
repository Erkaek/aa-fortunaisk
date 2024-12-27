# fortunaisk/tasks.py

# Standard Library
import logging

# Third Party
from celery import shared_task

# Django
from django.apps import apps
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def finalize_lottery(lottery_id: int) -> str:
    """
    Finalise une loterie en sélectionnant les gagnants, en mettant à jour le statut et en envoyant des notifications.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        if lottery.status != "active":
            logger.warning(
                f"Lottery {lottery.lottery_reference} not active. Status: {lottery.status}"
            )
            return "Lottery not active"

        winners = lottery.select_winners()
        if winners:
            lottery.notify_discord(winners)
        lottery.status = "completed"
        lottery.save(update_fields=["status"])

        logger.info(f"Loterie {lottery.lottery_reference} finalisée.")
        return f"Loterie {lottery.lottery_reference} finalisée."
    except Lottery.DoesNotExist:
        logger.error(f"Lottery {lottery_id} n'existe pas.")
        return "Lottery not found."
    except Exception as e:
        logger.exception(f"Erreur finalisant la loterie {lottery_id}: {e}")
        return "Error finalize_lottery"


@shared_task
def schedule_finalization(lottery_id: int):
    """
    Planifie la finalisation d'une loterie à sa date de fin.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        if lottery.status != "active":
            logger.warning(
                f"Lottery {lottery.lottery_reference} not active. Current status: {lottery.status}"
            )
            return

        # Calculer le temps restant jusqu'à la fin de la loterie
        now = timezone.now()
        delay = (lottery.end_date - now).total_seconds()

        if delay <= 0:
            # Si la date de fin est déjà passée, finaliser immédiatement
            finalize_lottery.delay(lottery.id)
            logger.info(
                f"Finalizing Lottery {lottery.lottery_reference} immediately as end_date is in the past."
            )
        else:
            # Planifier la tâche de finalisation
            finalize_lottery.apply_async(args=[lottery.id], countdown=delay)
            logger.info(
                f"Scheduled finalize_lottery for Lottery {lottery.lottery_reference} in {delay} seconds."
            )
    except Lottery.DoesNotExist:
        logger.error(f"Lottery ID {lottery_id} doesn't exist.")


@shared_task
def create_lottery_from_auto(auto_lottery_id: int) -> int | None:
    """
    Crée une Lottery à partir d'une AutoLottery donnée.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    AutoLotteryModel = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLotteryModel.objects.get(id=auto_lottery_id)
        if not auto_lottery.is_active:
            logger.warning(
                f"AutoLottery {auto_lottery.id} not active => skip creation."
            )
            return None

        start_date = timezone.now()
        end_date = start_date + auto_lottery.get_duration_timedelta()

        new_lottery = Lottery.objects.create(
            ticket_price=auto_lottery.ticket_price,
            start_date=start_date,
            end_date=end_date,
            payment_receiver=auto_lottery.payment_receiver,  # ForeignKey => OK
            winner_count=auto_lottery.winner_count,
            winners_distribution=auto_lottery.winners_distribution,
            max_tickets_per_user=auto_lottery.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=auto_lottery.duration_value,
            duration_unit=auto_lottery.duration_unit,
        )
        logger.info(
            f"Created Lottery '{new_lottery.lottery_reference}' from AutoLottery '{auto_lottery.name}'"
        )
        return new_lottery.id
    except AutoLotteryModel.DoesNotExist:
        logger.error(f"AutoLottery ID {auto_lottery_id} doesn't exist.")
    except Exception as e:
        logger.error(
            f"Error creating Lottery from AutoLottery {auto_lottery_id}: {str(e)}"
        )
    return None


def setup_periodic_tasks():
    """
    Configure les tâches périodiques par défaut pour FortunaIsk.
    """
    # Standard Library
    import json

    # Third Party
    from django_celery_beat.models import CrontabSchedule, PeriodicTask

    # check_lotteries => toutes les 15 minutes
    schedule_check, created = CrontabSchedule.objects.get_or_create(
        minute="*/15",
        hour="*",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
    )
    PeriodicTask.objects.update_or_create(
        name="check_lotteries",
        defaults={
            "task": "fortunaisk.tasks.check_lotteries",
            "crontab": schedule_check,
            "args": json.dumps([]),
        },
    )

    # process_wallet_tickets => toutes les 5 minutes
    schedule_wallet, created = CrontabSchedule.objects.get_or_create(
        minute="*/5",
        hour="*",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
    )
    PeriodicTask.objects.update_or_create(
        name="process_wallet_tickets",
        defaults={
            "task": "fortunaisk.tasks.process_wallet_tickets",
            "crontab": schedule_wallet,
            "args": json.dumps([]),
        },
    )

    # process_auto_lotteries => toutes les 60 minutes
    schedule_auto, created = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="*",
        day_of_month="*",
        month_of_year="*",
        day_of_week="*",
    )
    PeriodicTask.objects.update_or_create(
        name="process_auto_lotteries",
        defaults={
            "task": "fortunaisk.tasks.process_auto_lotteries",
            "crontab": schedule_auto,
            "args": json.dumps([]),
        },
    )

    logger.info("Periodic tasks configured successfully.")
