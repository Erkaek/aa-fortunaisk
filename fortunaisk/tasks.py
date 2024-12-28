# fortunaisk/tasks.py

# Standard Library
import json
import logging

# Third Party
from celery import shared_task

# Import nécessaires pour PeriodicTask et IntervalSchedule
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.apps import apps
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Vérifie les paiements contenant "lottery" dans la raison,
    crée des entrées TicketPurchase correspondantes et marque les paiements comme traités.
    """
    try:
        # Récupérer les paiements contenant "lottery" dans le champ reason et non traités
        CorporationWalletJournalEntryModel = apps.get_model(
            "corptools", "CorporationWalletJournalEntry"
        )
        pending_payments = (
            CorporationWalletJournalEntryModel.objects.select_for_update().filter(
                reason__icontains="lottery", processed=False
            )
        )

        logger.debug(f"Nombre de paiements en attente: {pending_payments.count()}")

        for payment in pending_payments:
            with transaction.atomic():
                try:
                    # Double-check if payment is still not processed
                    payment = CorporationWalletJournalEntryModel.objects.select_for_update().get(
                        id=payment.id
                    )
                    if payment.processed:
                        continue

                    # Étape 1 : Extraire les informations nécessaires
                    lottery_reference = payment.reason.strip().lower()
                    amount = payment.amount
                    payment_id = payment.entry_id

                    # Étape 2 : Trouver la loterie correspondante
                    Lottery = apps.get_model("fortunaisk", "Lottery")
                    try:
                        lottery = Lottery.objects.select_for_update().get(
                            lottery_reference=lottery_reference, status="active"
                        )
                    except Lottery.DoesNotExist:
                        logger.warning(
                            f"Aucune loterie active trouvée pour la référence '{lottery_reference}'. Paiement {payment_id} ignoré."
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly = apps.get_model("fortunaisk", "TicketAnomaly")
                        TicketAnomaly.objects.create(
                            lottery=None,  # Puisque Lottery n'existe pas
                            reason=f"Aucune loterie active trouvée pour la référence '{lottery_reference}'.",
                            payment_date=payment.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        payment.processed = True
                        payment.save(update_fields=["processed"])
                        continue

                    # Étape 3 : Trouver l'utilisateur
                    EveCharacter = apps.get_model("eveonline", "EveCharacter")
                    CharacterOwnership = apps.get_model(
                        "authentication", "CharacterOwnership"
                    )
                    UserProfile = apps.get_model("authentication", "UserProfile")

                    try:
                        # Trouver EveCharacter lié au paiement
                        eve_character = EveCharacter.objects.get(
                            character_id=payment.first_party_name_id
                        )

                        # Trouver CharacterOwnership
                        character_ownership = CharacterOwnership.objects.get(
                            character_id=eve_character.character_id
                        )

                        # Trouver UserProfile à partir de CharacterOwnership
                        user_profile = UserProfile.objects.get(
                            user_id=character_ownership.user_id
                        )

                        # Vérifier le personnage principal
                        if user_profile.main_character_id == eve_character.id:
                            user = user_profile.user
                        else:
                            logger.warning(
                                f"Personnage principal ({user_profile.main_character_id}) "
                                f"ne correspond pas à EveCharacter.id ({eve_character.id}) pour payment_id: {payment_id}"
                            )
                            # Enregistrer une anomalie
                            TicketAnomaly.objects.create(
                                lottery=lottery,
                                user=user_profile.user,
                                character=eve_character,
                                reason="Main character mismatch",
                                payment_date=payment.date,
                                amount=amount,
                                payment_id=payment_id,
                            )
                            # Marquer le paiement comme traité
                            payment.processed = True
                            payment.save(update_fields=["processed"])
                            continue

                    except EveCharacter.DoesNotExist:
                        logger.warning(
                            f"Aucun EveCharacter trouvé pour first_party_name_id: {payment.first_party_name_id}"
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            reason="EveCharacter does not exist",
                            payment_date=payment.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        payment.processed = True
                        payment.save(update_fields=["processed"])
                        continue
                    except CharacterOwnership.DoesNotExist:
                        logger.warning(
                            f"Aucun CharacterOwnership trouvé pour character_id: {eve_character.character_id}"
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=None,
                            character=eve_character,
                            reason="CharacterOwnership does not exist",
                            payment_date=payment.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        payment.processed = True
                        payment.save(update_fields=["processed"])
                        continue
                    except UserProfile.DoesNotExist:
                        logger.warning(
                            f"Aucun UserProfile trouvé pour user_id: {character_ownership.user_id}"
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=None,
                            character=eve_character,
                            reason="UserProfile does not exist",
                            payment_date=payment.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        payment.processed = True
                        payment.save(update_fields=["processed"])
                        continue

                    # Étape 4 : Vérifier le nombre de tickets de l'utilisateur
                    lottery_max_tickets = lottery.max_tickets_per_user
                    if lottery_max_tickets:
                        TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
                        user_ticket_count = TicketPurchase.objects.filter(
                            lottery=lottery, user=user
                        ).count()
                        if user_ticket_count >= lottery_max_tickets:
                            logger.warning(
                                f"User {user.username} has reached the maximum tickets for lottery {lottery.lottery_reference}."
                            )
                            # Enregistrer une anomalie
                            TicketAnomaly.objects.create(
                                lottery=lottery,
                                user=user,
                                character=eve_character,
                                reason="Max tickets per user exceeded",
                                payment_date=payment.date,
                                amount=amount,
                                payment_id=payment_id,
                            )
                            # Marquer le paiement comme traité
                            payment.processed = True
                            payment.save(update_fields=["processed"])
                            continue

                    # Étape 5 : Créer une entrée TicketPurchase
                    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
                    ticket_purchase = TicketPurchase.objects.create(
                        lottery=lottery,
                        user=user,
                        character=eve_character,  # Associer directement le personnage
                        amount=amount,
                        payment_id=str(payment_id),
                        status="processed",  # Set to processed directly
                    )

                    logger.info(
                        f"TicketPurchase {ticket_purchase.id} créé pour user '{user.username}' "
                        f"dans la loterie '{lottery.lottery_reference}'"
                    )

                    # Mise à jour des compteurs
                    lottery.participant_count = lottery.ticket_purchases.count()
                    lottery.total_pot = (
                        lottery.ticket_purchases.aggregate(total=Sum("amount"))["total"]
                        or 0
                    )
                    lottery.save(update_fields=["participant_count", "total_pot"])

                    # Étape 6 : Marquer le paiement comme traité
                    payment.processed = True
                    payment.save(update_fields=["processed"])

                except Exception as e:
                    logger.error(
                        f"Erreur lors du traitement du paiement {payment_id}: {e}"
                    )
                    # Optionally, retry the task
                    try:
                        self.retry(exc=e, countdown=60, max_retries=3)
                    except self.MaxRetriesExceededError:
                        logger.error(f"Max retries exceeded for payment {payment_id}")

        logger.info("check_purchased_tickets exécutée avec succès.")
    except Exception as e:
        logger.error(f"Erreur globale dans check_purchased_tickets: {e}")
        # Optionally, notify admins of failure


@shared_task(bind=True)
def check_lottery_status(self):
    """
    Vérifie l'état des loteries toutes les 15 minutes et clôture les loteries terminées.
    Avant de clôturer, revérifie les tickets achetés.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        now = timezone.now()
        active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
        logger.debug(
            f"Nombre de loteries actives à clôturer: {active_lotteries.count()}"
        )

        for lottery in active_lotteries:
            try:
                # Revérifier les tickets achetés si nécessaire
                logger.debug(
                    f"Revérification des tickets pour la loterie '{lottery.lottery_reference}'"
                )

                # Ici, on pourrait ajouter des vérifications spécifiques des tickets
                # Par exemple, vérifier si le montant correspond à un billet valide

                # Clôturer la loterie
                lottery.complete_lottery()
                logger.info(
                    f"Loterie '{lottery.lottery_reference}' clôturée avec succès."
                )

            except Exception as e:
                logger.error(
                    f"Erreur lors de la clôture de la loterie '{lottery.lottery_reference}': {e}"
                )
                # Optionally, notify admins of failure

        logger.info("check_lottery_status exécutée avec succès.")
    except Exception as e:
        logger.error(f"Erreur dans check_lottery_status: {e}")
        # Optionally, notify admins of failure


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_lottery_id: int):
    """
    Crée une Lottery basée sur une AutoLottery spécifique.
    """
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        new_lottery = auto_lottery.create_lottery()
        logger.info(
            f"Created Lottery '{new_lottery.lottery_reference}' from AutoLottery '{auto_lottery.name}'"
        )
        return new_lottery.id
    except AutoLottery.DoesNotExist:
        logger.error(
            f"AutoLottery avec l'ID {auto_lottery_id} n'existe pas ou est inactive."
        )
    except Exception as e:
        logger.error(
            f"Erreur lors de la création de la Lottery depuis l'AutoLottery {auto_lottery_id}: {e}"
        )
    return None


@shared_task(bind=True)
def finalize_lottery(self, lottery_id: int):
    """
    Finalise une Lottery une fois qu'elle est terminée.
    Sélectionne les gagnants, met à jour le statut et envoie des notifications.
    """
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        if lottery.status != "active":
            logger.info(
                f"Lottery '{lottery.lottery_reference}' is not active. Current status: {lottery.status}"
            )
            return

        # Sélectionner les gagnants
        winners = lottery.select_winners()
        logger.info(
            f"Selected {len(winners)} winners for Lottery '{lottery.lottery_reference}'"
        )

        if not winners:
            logger.warning(
                f"Aucun gagnant sélectionné pour la loterie {lottery.lottery_reference}."
            )
            lottery.status = "completed"
            lottery.save(update_fields=["status"])
            return

        # Mettre à jour le statut de la loterie
        lottery.status = "completed"
        lottery.save(update_fields=["status"])

        # Envoyer des notifications Discord pour les gagnants
        lottery.notify_discord(winners)

        logger.info(f"Lottery '{lottery.lottery_reference}' finalized successfully.")
    except Lottery.DoesNotExist:
        logger.error(f"Lottery avec l'ID {lottery_id} n'existe pas.")
    except Exception as e:
        logger.error(f"Erreur lors de la finalisation de la Lottery {lottery_id}: {e}")
        # Optionally, retry the task
        try:
            self.retry(exc=e, countdown=60, max_retries=3)
        except self.MaxRetriesExceededError:
            logger.error(
                f"Max retries exceeded for finalize_lottery task for lottery {lottery_id}"
            )


def setup_periodic_tasks():
    """
    Configure les tâches périodiques globales pour FortunaIsk.
    """
    # Vérifier si la tâche 'check_purchased_tickets' existe déjà
    if not PeriodicTask.objects.filter(name="check_purchased_tickets").exists():
        # check_purchased_tickets => toutes les 5 minutes
        schedule_check_tickets, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.create(
            name="check_purchased_tickets",
            task="fortunaisk.tasks.check_purchased_tickets",
            interval=schedule_check_tickets,
            args=json.dumps([]),
        )
        logger.info("Periodic task 'check_purchased_tickets' créée.")

    # Vérifier si la tâche 'check_lottery_status' existe déjà
    if not PeriodicTask.objects.filter(name="check_lottery_status").exists():
        # check_lottery_status => toutes les 15 minutes
        schedule_check_lottery, created = IntervalSchedule.objects.get_or_create(
            every=15,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.create(
            name="check_lottery_status",
            task="fortunaisk.tasks.check_lottery_status",
            interval=schedule_check_lottery,
            args=json.dumps([]),
        )
        logger.info("Periodic task 'check_lottery_status' créée.")

    logger.info("Periodic tasks globales configurées avec succès.")
