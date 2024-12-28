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

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def check_purchased_tickets(self):
    """
    Vérifie les paiements contenant "lottery" dans la raison,
    crée des entrées TicketPurchase correspondantes et marque les paiements comme traités.
    """
    logger.info("Démarrage de la tâche 'check_purchased_tickets'.")
    try:
        # Récupérer les modèles nécessaires avec les chemins d'importation corrects
        CorporationWalletJournalEntryModel = apps.get_model(
            "corptools", "CorporationWalletJournalEntry"
        )
        ProcessedPayment = apps.get_model("fortunaisk", "ProcessedPayment")
        TicketAnomaly = apps.get_model("fortunaisk", "TicketAnomaly")
        Lottery = apps.get_model("fortunaisk", "Lottery")
        EveCharacter = apps.get_model("eveonline", "EveCharacter")
        CharacterOwnership = apps.get_model(
            "authentication", "CharacterOwnership"
        )
        UserProfile = apps.get_model("authentication", "UserProfile")
        TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")

        # Récupérer les IDs des paiements déjà traités
        processed_payment_ids = list(
            ProcessedPayment.objects.values_list("payment_id", flat=True)
        )

        # Filtrer les paiements contenant "lottery" et non encore traités
        pending_payments = CorporationWalletJournalEntryModel.objects.filter(
            reason__icontains="lottery"
        ).exclude(entry_id__in=processed_payment_ids)

        logger.debug(f"Nombre de paiements en attente: {pending_payments.count()}")

        for payment in pending_payments:
            with transaction.atomic():
                try:
                    logger.debug(f"Traitement du paiement ID: {payment.id}")

                    # Verrouiller la ligne du paiement pour éviter les traitements concurrents
                    payment_locked = CorporationWalletJournalEntryModel.objects.select_for_update().get(
                        id=payment.id
                    )

                    # Re-vérifier si le paiement a déjà été traité
                    if ProcessedPayment.objects.filter(
                        payment_id=payment_locked.entry_id
                    ).exists():
                        logger.debug(
                            f"Le paiement ID {payment_locked.id} a déjà été traité. Passage au suivant."
                        )
                        continue

                    # Étape 1 : Extraire les informations nécessaires
                    lottery_reference = payment_locked.reason.strip().lower()
                    amount = payment_locked.amount
                    payment_id = payment_locked.entry_id

                    logger.debug(
                        f"Extraction des informations du paiement ID {payment_id}: "
                        f"référence loterie='{lottery_reference}', montant={amount}"
                    )

                    # Étape 2 : Trouver la loterie correspondante
                    try:
                        lottery = Lottery.objects.select_for_update().get(
                            lottery_reference=lottery_reference, status="active"
                        )
                        logger.debug(
                            f"Loterie trouvée pour la référence '{lottery_reference}': ID {lottery.id}"
                        )
                    except Lottery.DoesNotExist:
                        logger.warning(
                            f"Aucune loterie active trouvée pour la référence '{lottery_reference}'. "
                            f"Paiement ID {payment_id} ignoré."
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=None,  # Maintenant accepté
                            reason=f"Aucune loterie active trouvée pour la référence '{lottery_reference}'.",
                            payment_date=payment_locked.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité en créant une entrée dans ProcessedPayment
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Paiement ID {payment_id} marqué comme traité suite à l'anomalie."
                        )
                        continue

                    # Étape 3 : Trouver l'utilisateur et le main character
                    try:
                        logger.debug(
                            f"Recherche de l'EveCharacter avec character_id={payment_locked.first_party_name_id}."
                        )
                        # Trouver EveCharacter lié au paiement
                        eve_character = EveCharacter.objects.get(
                            character_id=payment_locked.first_party_name_id
                        )
                        logger.debug(
                            f"EveCharacter trouvé: ID {eve_character.id} pour le paiement ID {payment_id}."
                        )

                        # Trouver CharacterOwnership en traversant la relation ForeignKey
                        character_ownership = CharacterOwnership.objects.get(
                            character__character_id=eve_character.character_id
                        )
                        logger.debug(
                            f"CharacterOwnership trouvé: user_id={character_ownership.user_id} pour le personnage ID {eve_character.character_id}."
                        )

                        # Trouver UserProfile à partir de CharacterOwnership
                        user_profile = UserProfile.objects.get(
                            user_id=character_ownership.user_id
                        )
                        logger.debug(
                            f"UserProfile trouvé: user_id={user_profile.user_id} associé au CharacterOwnership."
                        )

                        # Récupérer le personnage principal (Main Character)
                        main_character_id = user_profile.main_character_id
                        main_eve_character = EveCharacter.objects.get(
                            id=main_character_id
                        )
                        main_character_name = main_eve_character.character_name

                        user = user_profile.user
                        logger.debug(
                            f"Personnage principal récupéré: ID {main_character_id}, Nom '{main_character_name}' pour l'utilisateur '{user.username}'."
                        )

                    except EveCharacter.DoesNotExist:
                        logger.warning(
                            f"Aucun EveCharacter trouvé pour first_party_name_id: {payment_locked.first_party_name_id}."
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            reason="EveCharacter does not exist",
                            payment_date=payment_locked.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Paiement ID {payment_id} marqué comme traité suite à l'absence d'EveCharacter."
                        )
                        continue
                    except CharacterOwnership.DoesNotExist:
                        logger.warning(
                            f"Aucun CharacterOwnership trouvé pour character_id: {eve_character.character_id}."
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=None,
                            character=eve_character,
                            reason="CharacterOwnership does not exist",
                            payment_date=payment_locked.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Paiement ID {payment_id} marqué comme traité suite à l'absence de CharacterOwnership."
                        )
                        continue
                    except UserProfile.DoesNotExist:
                        logger.warning(
                            f"Aucun UserProfile trouvé pour user_id: {character_ownership.user_id}."
                        )
                        # Enregistrer une anomalie
                        TicketAnomaly.objects.create(
                            lottery=lottery,
                            user=None,
                            character=eve_character,
                            reason="UserProfile does not exist",
                            payment_date=payment_locked.date,
                            amount=amount,
                            payment_id=payment_id,
                        )
                        # Marquer le paiement comme traité
                        ProcessedPayment.objects.create(payment_id=payment_id)
                        logger.info(
                            f"Paiement ID {payment_id} marqué comme traité suite à l'absence de UserProfile."
                        )
                        continue

                    # Étape 4 : Vérifier le nombre de tickets de l'utilisateur (regroupé sur le main character)
                    lottery_max_tickets = lottery.max_tickets_per_user
                    if lottery_max_tickets:
                        user_ticket_count = TicketPurchase.objects.filter(
                            lottery=lottery,
                            user=user,
                            character__id=user_profile.main_character_id,
                        ).count()
                        logger.debug(
                            f"Utilisateur '{user.username}' possède actuellement {user_ticket_count} tickets "
                            f"pour la loterie '{lottery.lottery_reference}' (Main Character: {main_character_name})."
                        )
                        if user_ticket_count >= lottery_max_tickets:
                            logger.warning(
                                f"Utilisateur '{user.username}' a atteint le nombre maximum de tickets "
                                f"({lottery_max_tickets}) pour la loterie '{lottery.lottery_reference}'."
                            )
                            # Enregistrer une anomalie
                            TicketAnomaly.objects.create(
                                lottery=lottery,
                                user=user,
                                character=eve_character,
                                reason="Max tickets per user exceeded",
                                payment_date=payment_locked.date,
                                amount=amount,
                                payment_id=payment_id,
                            )
                            # Marquer le paiement comme traité
                            ProcessedPayment.objects.create(payment_id=payment_id)
                            logger.info(
                                f"Paiement ID {payment_id} marqué comme traité suite au dépassement du nombre de tickets."
                            )
                            continue

                    # Étape 5 : Créer une entrée TicketPurchase
                    ticket_purchase = TicketPurchase.objects.create(
                        lottery=lottery,
                        user=user,
                        character=eve_character,  # Associer directement le personnage
                        amount=amount,
                        payment_id=str(payment_id),
                        status="processed",  # Set to processed directly
                    )

                    logger.info(
                        f"TicketPurchase ID {ticket_purchase.id} créé pour l'utilisateur '{user.username}' "
                        f"dans la loterie '{lottery.lottery_reference}'."
                    )

                    # Mise à jour des compteurs
                    previous_participant_count = lottery.participant_count
                    previous_total_pot = lottery.total_pot

                    lottery.participant_count = lottery.ticket_purchases.count()
                    lottery.total_pot = (
                        lottery.ticket_purchases.aggregate(total=Sum("amount"))["total"]
                        or 0
                    )
                    lottery.save(update_fields=["participant_count", "total_pot"])

                    logger.debug(
                        f"Mise à jour de la loterie '{lottery.lottery_reference}': "
                        f"participant_count: {previous_participant_count} -> {lottery.participant_count}, "
                        f"total_pot: {previous_total_pot} -> {lottery.total_pot}."
                    )

                    # Étape 6 : Marquer le paiement comme traité en créant une entrée dans ProcessedPayment
                    ProcessedPayment.objects.create(payment_id=payment_id)
                    logger.info(
                        f"Paiement ID {payment_id} marqué comme traité avec succès."
                    )

                except Exception as e:
                    logger.error(
                        f"Erreur lors du traitement du paiement ID {payment_id}: {e}",
                        exc_info=True,
                    )
                    # Optionally, retry the task
                    try:
                        self.retry(exc=e, countdown=60, max_retries=3)
                        logger.debug(
                            f"Requête de réexécution de la tâche pour le paiement ID {payment_id}."
                        )
                    except self.MaxRetriesExceededError:
                        logger.error(
                            f"Nombre maximal de tentatives dépassé pour le paiement ID {payment_id}."
                        )
    except Exception as outer_e:
        logger.critical(
            f"Erreur générale dans la tâche 'check_purchased_tickets': {outer_e}",
            exc_info=True,
        )
        # Optionally, notify admins of failure


@shared_task(bind=True)
def check_lottery_status(self):
    """
    Vérifie l'état des loteries toutes les 15 minutes et clôture les loteries terminées.
    Avant de clôturer, revérifie les tickets achetés.
    """
    logger.info("Démarrage de la tâche 'check_lottery_status'.")
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        now = timezone.now()
        active_lotteries = Lottery.objects.filter(status="active", end_date__lte=now)
        logger.debug(
            f"Nombre de loteries actives à clôturer: {active_lotteries.count()}"
        )

        for lottery in active_lotteries:
            try:
                logger.debug(
                    f"Début de la clôture de la loterie '{lottery.lottery_reference}' (ID {lottery.id})."
                )
                # Revérifier les tickets achetés si nécessaire
                logger.debug(
                    f"Revérification des tickets pour la loterie '{lottery.lottery_reference}'."
                )

                # Ici, on pourrait ajouter des vérifications spécifiques des tickets
                # Par exemple, vérifier si le montant correspond à un billet valide

                # Clôturer la loterie
                lottery.complete_lottery()
                logger.info(
                    f"Loterie '{lottery.lottery_reference}' (ID {lottery.id}) clôturée avec succès."
                )

            except Exception as e:
                logger.error(
                    f"Erreur lors de la clôture de la loterie '{lottery.lottery_reference}' (ID {lottery.id}): {e}",
                    exc_info=True,
                )
                # Optionally, notify admins of failure

        logger.info(
            "Exécution de la tâche 'check_lottery_status' terminée avec succès."
        )
    except Exception as e:
        logger.critical(
            f"Erreur dans la tâche 'check_lottery_status': {e}", exc_info=True
        )
        # Optionally, notify admins of failure


@shared_task(bind=True)
def create_lottery_from_auto_lottery(self, auto_lottery_id: int):
    """
    Crée une Lottery basée sur une AutoLottery spécifique.
    """
    logger.info(
        f"Démarrage de la tâche 'create_lottery_from_auto_lottery' pour AutoLottery ID {auto_lottery_id}."
    )
    AutoLottery = apps.get_model("fortunaisk", "AutoLottery")
    try:
        auto_lottery = AutoLottery.objects.get(id=auto_lottery_id, is_active=True)
        logger.debug(
            f"AutoLottery trouvé: ID {auto_lottery.id}, nom='{auto_lottery.name}'. Création de la Lottery associée."
        )
        new_lottery = auto_lottery.create_lottery()
        logger.info(
            f"Lottery '{new_lottery.lottery_reference}' (ID {new_lottery.id}) créée à partir de l'AutoLottery '{auto_lottery.name}' (ID {auto_lottery.id})."
        )
        return new_lottery.id
    except AutoLottery.DoesNotExist:
        logger.error(
            f"AutoLottery avec l'ID {auto_lottery_id} n'existe pas ou est inactive."
        )
    except Exception as e:
        logger.error(
            f"Erreur lors de la création de la Lottery depuis l'AutoLottery ID {auto_lottery_id}: {e}",
            exc_info=True,
        )
    return None


@shared_task(bind=True)
def finalize_lottery(self, lottery_id: int):
    """
    Finalise une Lottery une fois qu'elle est terminée.
    Sélectionne les gagnants, met à jour le statut et envoie des notifications.
    """
    logger.info(
        f"Démarrage de la tâche 'finalize_lottery' pour Lottery ID {lottery_id}."
    )
    Lottery = apps.get_model("fortunaisk", "Lottery")
    try:
        lottery = Lottery.objects.get(id=lottery_id)
        logger.debug(
            f"Lottery trouvé: '{lottery.lottery_reference}' (ID {lottery.id}), statut actuel: '{lottery.status}'."
        )
        if lottery.status != "active":
            logger.info(
                f"Lottery '{lottery.lottery_reference}' (ID {lottery.id}) n'est pas active. Statut actuel: '{lottery.status}'. Aucune action effectuée."
            )
            return

        # Sélectionner les gagnants
        winners = lottery.select_winners()
        logger.info(
            f"{len(winners)} gagnant(s) sélectionné(s) pour la Lottery '{lottery.lottery_reference}' (ID {lottery.id})."
        )

        if not winners:
            logger.warning(
                f"Aucun gagnant sélectionné pour la loterie '{lottery.lottery_reference}' (ID {lottery.id})."
            )
            lottery.status = "completed"
            lottery.save(update_fields=["status"])
            logger.info(
                f"Loterie '{lottery.lottery_reference}' (ID {lottery.id}) marquée comme 'completed' sans gagnants."
            )
            return

        # Mettre à jour le statut de la loterie
        lottery.status = "completed"
        lottery.save(update_fields=["status"])
        logger.debug(
            f"Statut de la loterie '{lottery.lottery_reference}' (ID {lottery.id}) mis à jour en 'completed'."
        )

        # Envoyer des notifications Discord pour les gagnants
        lottery.notify_discord(winners)
        logger.info(
            f"Notifications Discord envoyées pour les gagnants de la loterie '{lottery.lottery_reference}' (ID {lottery.id})."
        )

        logger.info(
            f"Finalisation de la loterie '{lottery.lottery_reference}' (ID {lottery.id}) terminée avec succès."
        )
    except Lottery.DoesNotExist:
        logger.error(f"Lottery avec l'ID {lottery_id} n'existe pas.")
    except Exception as e:
        logger.error(
            f"Erreur lors de la finalisation de la Lottery ID {lottery_id}: {e}",
            exc_info=True,
        )
        # Optionally, retry the task
        try:
            self.retry(exc=e, countdown=60, max_retries=3)
            logger.debug(
                f"Requête de réexécution de la tâche 'finalize_lottery' pour Lottery ID {lottery_id}."
            )
        except self.MaxRetriesExceededError:
            logger.error(
                f"Nombre maximal de tentatives dépassé pour la tâche 'finalize_lottery' de la Lottery ID {lottery_id}."
            )


def setup_periodic_tasks():
    """
    Configure les tâches périodiques globales pour FortunaIsk.
    """
    logger.info("Configuration des tâches périodiques globales pour FortunaIsk.")
    try:
        # Récupérer les modèles nécessaires
        IntervalScheduleModel = apps.get_model("django_celery_beat", "IntervalSchedule")
        PeriodicTaskModel = apps.get_model("django_celery_beat", "PeriodicTask")

        # Vérifier si la tâche 'check_purchased_tickets' existe déjà
        if not PeriodicTaskModel.objects.filter(
            name="check_purchased_tickets"
        ).exists():
            # check_purchased_tickets => toutes les 5 minutes
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
                logger.debug("IntervalSchedule créée pour 'check_purchased_tickets'.")
            logger.info("Tâche périodique 'check_purchased_tickets' créée.")

        else:
            logger.debug("La tâche périodique 'check_purchased_tickets' existe déjà.")

        # Vérifier si la tâche 'check_lottery_status' existe déjà
        if not PeriodicTaskModel.objects.filter(name="check_lottery_status").exists():
            # check_lottery_status => toutes les 15 minutes
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
                logger.debug("IntervalSchedule créée pour 'check_lottery_status'.")
            logger.info("Tâche périodique 'check_lottery_status' créée.")

        else:
            logger.debug("La tâche périodique 'check_lottery_status' existe déjà.")

        logger.info(
            "Configuration des tâches périodiques globales terminée avec succès."
        )
    except Exception as e:
        logger.critical(
            f"Erreur lors de la configuration des tâches périodiques: {e}",
            exc_info=True,
        )
        # Optionally, notify admins of failure
