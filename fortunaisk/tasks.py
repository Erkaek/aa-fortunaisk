# fortunaisk/tasks.py

# Standard Library
import json
import logging

# Third Party
from celery import shared_task

# Importer les modèles nécessaires
from corptools.models import CorporationWalletJournalEntry
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.apps import apps
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def check_purchased_tickets():
    """
    Vérifie les paiements contenant "lottery" dans la raison,
    crée des entrées TicketPurchase correspondantes et marque les paiements comme traités.
    """
    try:
        # Récupérer les paiements contenant "lottery" dans le champ reason
        pending_payments = CorporationWalletJournalEntry.objects.filter(
            reason__icontains="lottery"
        )

        logger.debug(f"Nombre de paiements en attente: {pending_payments.count()}")

        for payment in pending_payments:
            with transaction.atomic():
                try:
                    # Étape 1 : Extraire les informations nécessaires
                    lottery_reference = payment.reason.strip()
                    amount = payment.amount
                    payment_id = payment.entry_id

                    # Étape 2 : Trouver la loterie correspondante
                    Lottery = apps.get_model("fortunaisk", "Lottery")
                    try:
                        lottery = Lottery.objects.get(
                            lottery_reference=lottery_reference, status="active"
                        )
                    except Lottery.DoesNotExist:
                        logger.warning(
                            f"Aucune loterie active trouvée pour la référence '{lottery_reference}'. Paiement {payment_id} ignoré."
                        )
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
                            continue

                    except EveCharacter.DoesNotExist:
                        logger.warning(
                            f"Aucun EveCharacter trouvé pour first_party_name_id: {payment.first_party_name_id}"
                        )
                        continue
                    except CharacterOwnership.DoesNotExist:
                        logger.warning(
                            f"Aucun CharacterOwnership trouvé pour character_id: {eve_character.character_id}"
                        )
                        continue
                    except UserProfile.DoesNotExist:
                        logger.warning(
                            f"Aucun UserProfile trouvé pour user_id: {character_ownership.user_id}"
                        )
                        continue

                    # Étape 4 : Créer une entrée TicketPurchase
                    TicketPurchase = apps.get_model("fortunaisk", "TicketPurchase")
                    ticket_purchase = TicketPurchase.objects.create(
                        lottery=lottery,
                        user=user,
                        character=eve_character,  # Associer directement le personnage
                        amount=amount,
                        payment_id=str(payment_id),
                        status="pending",
                    )

                    logger.info(
                        f"TicketPurchase {ticket_purchase.id} créé pour user '{user.username}' "
                        f"dans la loterie '{lottery.lottery_reference}'"
                    )

                    # Étape 5 : Marquer le paiement comme traité
                    payment.processed = True
                    payment.save(update_fields=["processed"])

                except Exception as e:
                    logger.error(
                        f"Erreur lors du traitement du paiement {payment_id}: {e}"
                    )

        logger.info("check_purchased_tickets exécutée avec succès.")
    except Exception as e:
        logger.error(f"Erreur globale dans check_purchased_tickets: {e}")


@shared_task
def check_lottery_status():
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
                tickets = lottery.ticket_purchases.all()
                logger.debug(
                    f"Revérification des tickets pour la loterie '{lottery.lottery_reference}'"
                )

                for ticket in tickets:
                    logger.debug(
                        f"Checking ticket {ticket.id} for user '{ticket.user.username}'"
                    )
                    # Ajoutez votre logique de revérification ici si nécessaire

                # Clôturer la loterie
                lottery.complete_lottery()
                logger.info(
                    f"Loterie '{lottery.lottery_reference}' clôturée avec succès."
                )

            except Exception as e:
                logger.error(
                    f"Erreur lors de la clôture de la loterie '{lottery.lottery_reference}': {e}"
                )

        logger.info("check_lottery_status exécutée avec succès.")
    except Exception as e:
        logger.error(f"Erreur dans check_lottery_status: {e}")


@shared_task
def create_lottery_from_auto_lottery(auto_lottery_id: int):
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


@shared_task
def finalize_lottery(lottery_id: int):
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
