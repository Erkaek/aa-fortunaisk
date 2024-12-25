# fortunaisk/tasks.py

# Standard Library
import logging

# Third Party
from celery import shared_task

# Django
from django.apps import apps  # type: ignore
from django.db import IntegrityError  # type: ignore
from django.utils import timezone  # type: ignore

# fortunaisk
from fortunaisk.models import TicketAnomaly, TicketPurchase

logger = logging.getLogger(__name__)


@shared_task
def check_lotteries() -> str:
    """
    Vérifie toutes les loteries actives dont la date de fin est dépassée et les termine.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    now = timezone.now()
    active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
    count = active_lotteries.count()
    for lottery in active_lotteries:
        lottery.complete_lottery()
    return f"Vérifiées {count} loterie(s)."


@shared_task
def create_lottery_from_auto(auto_lottery_id: int) -> int | None:
    """
    Crée une nouvelle Loterie à partir d'une AutoLoterie (planifiée avec Celery).
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    AutoLotteryModel = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLotteryModel.objects.get(id=auto_lottery_id)

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
            f"Créée nouvelle Loterie '{new_lottery.lottery_reference}' "
            f"à partir de l'AutoLoterie '{auto_lottery.name}' (ID: {auto_lottery_id})"
        )
        return new_lottery.id

    except AutoLotteryModel.DoesNotExist:
        logger.error(f"AutoLoterie avec ID {auto_lottery_id} n'existe pas.")
    except Exception as e:
        logger.error(
            f"Erreur lors de la création de la Loterie à partir de l'AutoLoterie {auto_lottery_id} : {str(e)}"
        )
    return None


@shared_task
def finalize_lottery(lottery_id: int) -> str:
    """
    Finalise la loterie en sélectionnant les gagnants et en envoyant les notifications.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        if lottery.status != "active":
            return f"Loterie {lottery.lottery_reference} n'est pas active."

        # Sélection des gagnants
        winners = lottery.select_winners()
        # Envoi des notifications Discord
        lottery.notify_discord(winners)

        return f"Loterie {lottery.lottery_reference} finalisée avec succès."
    except Lottery.DoesNotExist:
        logger.error(f"Loterie avec ID {lottery_id} n'existe pas.")
        return f"Loterie avec ID {lottery_id} n'existe pas."
    except Exception as e:
        logger.exception(
            f"Erreur lors de la finalisation de la loterie {lottery_id} : {e}"
        )
        return f"Erreur lors de la finalisation de la loterie {lottery_id}."


@shared_task
def process_wallet_tickets() -> str:
    """
    Traite les entrées de portefeuille pour toutes les loteries actives.
    Correspond les entrées de CorporationWalletJournalEntry pour créer des TicketPurchase ou des anomalies.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    EveCharacter = apps.get_model("eveonline", "EveCharacter")  # Correction ici
    CorporationWalletJournalEntry = apps.get_model(
        "corptools", "CorporationWalletJournalEntry"
    )

    logger.info("Traitement des entrées de portefeuille pour les loteries actives.")
    active_lotteries = Lottery.objects.filter(status="active")
    total_processed = 0

    if not active_lotteries.exists():
        return "Aucune loterie active à traiter."

    for lottery in active_lotteries:
        reason_filter = ""
        if lottery.lottery_reference:
            # Par exemple, "LOTTERY-123456" => raison pourrait contenir "123456"
            reason_filter = lottery.lottery_reference.replace("LOTTERY-", "")

        # Correspondance stricte sur le montant et correspondance partielle sur la raison
        payments = CorporationWalletJournalEntry.objects.filter(
            second_party_name_id=lottery.payment_receiver,
            amount=lottery.ticket_price,  # Assure que le montant correspond au prix du ticket
            reason__icontains=reason_filter,
        ).select_related("first_party_name")

        for payment in payments:
            # Identifier les anomalies potentielles
            anomaly_reason = None
            eve_character = None
            user = None
            payment_id_str = str(payment.id)

            # Vérifier si une anomalie est déjà enregistrée
            if TicketAnomaly.objects.filter(
                lottery=lottery, payment_id=payment_id_str
            ).exists():
                logger.info(
                    f"Anomalie déjà enregistrée pour le paiement {payment_id_str}, passage."
                )
                continue

            # Vérifier la plage de dates
            if not (lottery.start_date <= payment.date <= lottery.end_date):
                anomaly_reason = "Date de paiement en dehors de la période de loterie."

            # Identifier le personnage
            try:
                eve_character = EveCharacter.objects.get(
                    character_id=payment.first_party_name_id
                )
                ownership = eve_character.character_ownership
                if not ownership or not ownership.user:
                    if anomaly_reason is None:
                        anomaly_reason = (
                            "Aucun utilisateur principal pour le personnage."
                        )
                else:
                    user = ownership.user
                    # Vérifier le nombre maximum de tickets par utilisateur
                    user_ticket_count = TicketPurchase.objects.filter(
                        user=user, lottery=lottery
                    ).count()
                    if lottery.max_tickets_per_user is not None:
                        if user_ticket_count >= lottery.max_tickets_per_user:
                            if anomaly_reason is None:
                                anomaly_reason = (
                                    f"L'utilisateur '{user.username}' a dépassé le nombre maximum de tickets "
                                    f"({lottery.max_tickets_per_user})."
                                )
            except EveCharacter.DoesNotExist:
                if anomaly_reason is None:
                    anomaly_reason = (
                        f"EveCharacter {payment.first_party_name_id} non trouvé."
                    )

            # Enregistrer l'anomalie si trouvée
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
                logger.info(f"Anomalie détectée : {anomaly_reason}")
                continue

            # Sinon, créer le TicketPurchase avec le montant correct
            try:
                TicketPurchase.objects.create(
                    user=user,
                    lottery=lottery,
                    character=eve_character,
                    amount=lottery.ticket_price,  # Fixe le montant au prix du ticket
                    purchase_date=timezone.now(),
                    payment_id=payment_id_str,
                )
                logger.info(f"Ticket enregistré pour l'utilisateur '{user.username}'.")
                total_processed += 1
            except IntegrityError as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=f"Erreur d'intégrité : {e}",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                logger.error(
                    f"Erreur d'intégrité lors du traitement du paiement {payment_id_str} : {e}"
                )
            except Exception as e:
                TicketAnomaly.objects.create(
                    lottery=lottery,
                    character=eve_character,
                    user=user,
                    reason=f"Erreur inattendue : {e}",
                    payment_date=payment.date,
                    amount=payment.amount,
                    payment_id=payment_id_str,
                )
                logger.exception(
                    f"Erreur inattendue lors du traitement du paiement {payment_id_str} : {e}"
                )

    return f"{total_processed} ticket(s) traité(s) pour toutes les loteries actives."
