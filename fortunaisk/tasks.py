# fortunaisk/tasks.py

# Standard Library
import logging

# Third Party
from celery import shared_task

# Django
from django.apps import apps
from django.db import IntegrityError
from django.utils import timezone

# fortunaisk
from fortunaisk.models import TicketAnomaly, TicketPurchase

logger = logging.getLogger(__name__)


@shared_task
def check_lotteries() -> str:
    Lottery = apps.get_model("fortunaisk", "Lottery")
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
    count = active_lotteries.count()
    for lottery in active_lotteries:
        lottery.complete_lottery()
    return f"Vérifiées {count} loterie(s)."


@shared_task
def create_lottery_from_auto(auto_lottery_id: int) -> int | None:
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
            payment_receiver=auto_lottery.payment_receiver,
            winner_count=auto_lottery.winner_count,
            winners_distribution=auto_lottery.winners_distribution,
            max_tickets_per_user=auto_lottery.max_tickets_per_user,  # None => illimité
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


@shared_task
def finalize_lottery(lottery_id: int) -> str:
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        if lottery.status != "active":
            logger.warning(
                f"Lottery {lottery.lottery_reference} not active. Status: {lottery.status}"
            )
            # On retire le `f` pour éviter F541
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
        logger.exception(f"Erreur finalisant la lottery {lottery_id}: {e}")
        return "Error finalize_lottery"


@shared_task
def process_wallet_tickets() -> str:
    Lottery = apps.get_model("fortunaisk", "Lottery")
    EveCharacter = apps.get_model("eveonline", "EveCharacter")
    CorporationWalletJournalEntry = apps.get_model(
        "corptools", "CorporationWalletJournalEntry"
    )

    logger.info("Traitement des entrées de portefeuille pour les loteries actives.")
    active_lotteries = Lottery.objects.filter(status="active")
    total_processed = 0

    if not active_lotteries.exists():
        return "Aucune loterie active."

    for lottery in active_lotteries:
        reason_filter = ""
        if lottery.lottery_reference:
            reason_filter = lottery.lottery_reference.replace("LOTTERY-", "")

        # Filtrage approximatif
        payments = CorporationWalletJournalEntry.objects.filter(
            second_party_name_id=(
                lottery.payment_receiver.corporation_id
                if lottery.payment_receiver
                else 0
            ),
            amount=lottery.ticket_price,
            reason__icontains=reason_filter,
        ).select_related("first_party_name")

        for payment in payments:
            payment_id_str = str(payment.id)

            # Déjà traité ?
            if (
                TicketAnomaly.objects.filter(
                    lottery=lottery, payment_id=payment_id_str
                ).exists()
                or TicketPurchase.objects.filter(payment_id=payment_id_str).exists()
            ):
                continue

            # check date
            if not (lottery.start_date <= payment.date <= lottery.end_date):
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    reason="Date de paiement hors loterie",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                continue

            # identif personnage
            try:
                eve_character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = eve_character.character_ownership
                user = ownership.user if ownership else None
            except EveCharacter.DoesNotExist:
                # Anomalie => pas de personnage
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    reason="EveCharacter introuvable",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                continue

            if user is None:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    reason="Aucun user rattaché à ce personnage",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                continue

            # check max tickets
            if lottery.max_tickets_per_user is not None:
                user_ticket_count = TicketPurchase.objects.filter(
                    user=user, lottery=lottery
                ).count()
                if user_ticket_count >= lottery.max_tickets_per_user:
                    TicketAnomaly.objects.create(
                        lottery=lottery,
                        character=eve_character,
                        user=user,
                        reason="User a dépassé le max de tickets",
                        payment_date=payment.date,
                        amount=payment.amount,
                        payment_id=payment_id_str,
                    )
                    continue

            # Sinon => on crée le ticket
            try:
                TicketPurchase.objects.create(
                    user=user,
                    lottery=lottery,
                    character=eve_character,
                    amount=lottery.ticket_price,
                    purchase_date=timezone.now(),
                    payment_id=payment_id_str,
                )
                logger.info(
                    f"Ticket enregistré pour user={user.username}, lottery={lottery.lottery_reference}."
                )
                total_processed += 1
            except IntegrityError as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=f"IntegrityError: {e}",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
            except Exception as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=f"Unexpected Error: {e}",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )

    return f"{total_processed} ticket(s) traités."
