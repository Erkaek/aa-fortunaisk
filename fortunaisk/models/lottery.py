# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import Decimal

# Third Party
from celery import chain

# Django
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models.ticket import TicketPurchase, Winner
from fortunaisk.tasks import finalize_lottery, process_wallet_tickets

logger = logging.getLogger(__name__)


class Lottery(models.Model):
    """
    Représente une instance unique de loterie.
    Supporte plusieurs gagnants basés sur une distribution.
    """

    DURATION_UNITS = [
        ("hours", "Heures"),
        ("days", "Jours"),
        ("months", "Mois"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Terminée"),
        ("cancelled", "Annulée"),
    ]

    ticket_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Prix du Ticket (ISK)",
        help_text="Prix d'un ticket de loterie en ISK.",
    )
    start_date = models.DateTimeField(verbose_name="Date de Début")
    end_date = models.DateTimeField(db_index=True, verbose_name="Date de Fin")
    payment_receiver = models.IntegerField(
        db_index=True,
        verbose_name="ID du Récepteur de Paiement",
        help_text="ID de la corporation ou du personnage qui reçoit les paiements en ISK.",
    )
    lottery_reference = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Référence de la Loterie",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
        verbose_name="Statut de la Loterie",
    )
    winners_distribution = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Distribution des Gagnants",
        help_text="Liste des répartitions en pourcentage pour les gagnants (la somme doit être 100).",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Tickets Maximum par Utilisateur"
    )
    total_pot = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=0,
        verbose_name="Total Pot (ISK)",
        help_text="Pot cumulatif en ISK provenant des achats de tickets.",
    )
    duration_value = models.PositiveIntegerField(
        default=24,
        verbose_name="Valeur de Durée",
        help_text="Valeur numérique de la durée de la loterie.",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        verbose_name="Unité de Durée",
        help_text="Unité de temps pour la durée de la loterie.",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Nombre de Gagnants"
    )

    class Meta:
        ordering = ["-start_date"]
        permissions = [
            ("view_lotteryhistory", "Peut voir l'historique des loteries"),
            ("terminate_lottery", "Peut terminer une loterie"),
            ("admin_dashboard", "Peut accéder au tableau de bord admin"),
        ]

    def __str__(self) -> str:
        return f"Loterie {self.lottery_reference} [{self.status}]"

    @staticmethod
    def generate_unique_reference() -> str:
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def clean(self):
        """
        Assure que la distribution des gagnants est valide.
        """
        if self.winners_distribution:
            if len(self.winners_distribution) != self.winner_count:
                logger.error("Mismatch between winners_distribution and winner_count.")
                raise ValueError(
                    "Mismatch between winners_distribution and winner_count."
                )
            total_percentage = sum(self.winners_distribution)
            logger.debug(f"Sum of winners_distribution: {total_percentage}")
            if round(total_percentage, 2) != 100.0:
                logger.error("Sum of winners_distribution must equal 100.")
                raise ValueError("Sum of winners_distribution must equal 100.")

    def save(self, *args, **kwargs) -> None:
        self.clean()
        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self) -> timedelta:
        """
        Calcule la durée de la loterie sous forme de timedelta.
        """
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(
                days=30 * self.duration_value
            )  # Approximation de 30 jours par mois.
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """
        Met à jour le total_pot basé sur le nombre de tickets et le prix du ticket.
        """
        ticket_count = self.ticket_purchases.count()
        logger.debug(
            f"Loterie {self.lottery_reference} - Nombre de tickets: {ticket_count}"
        )
        self.total_pot = self.ticket_price * Decimal(ticket_count)
        self.save(update_fields=["total_pot"])
        logger.debug(
            f"Loterie {self.lottery_reference} - Total Pot mis à jour: {self.total_pot} ISK"
        )

    def complete_lottery(self):
        if self.status != "active":
            logger.info(
                f"Loterie {self.lottery_reference} n'est pas active. Statut actuel: {self.status}"
            )
            return

        # Mettre à jour le pot total
        self.update_total_pot()
        logger.debug(
            f"Loterie {self.lottery_reference} - Total Pot recalculé: {self.total_pot} ISK"
        )

        if self.total_pot <= Decimal("0"):
            logger.error(
                f"Loterie {self.lottery_reference} a un pot total de {self.total_pot} ISK. Abandon de la distribution des prix."
            )
            self.status = "completed"
            self.save(update_fields=["status"])
            return

        # Créer une chaîne de tâches : d'abord traiter les tickets, puis finaliser la loterie
        task_chain = chain(process_wallet_tickets.s(), finalize_lottery.s(self.id))
        task_chain.apply_async()
        logger.info(
            f"Chaîne de tâches lancée pour la loterie {self.lottery_reference}."
        )

    def select_winners(self):
        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            logger.info(
                f"Aucun ticket trouvé pour la loterie {self.lottery_reference}."
            )
            return []

        winners = []
        selected_ticket_ids = set()
        for idx, percentage in enumerate(self.winners_distribution):
            if idx >= self.winner_count:
                break
            # Assurer des gagnants uniques
            available_tickets = tickets.exclude(id__in=selected_ticket_ids)
            if not available_tickets.exists():
                logger.warning(
                    f"Plus de tickets disponibles pour la loterie {self.lottery_reference}."
                )
                break
            random_ticket = available_tickets.order_by("?").first()
            if random_ticket:
                selected_ticket_ids.add(random_ticket.id)
                # Conversion de percentage en Decimal
                percentage_decimal = Decimal(str(percentage))
                prize_amount = (self.ticket_price * percentage_decimal) / Decimal("100")
                prize_amount = prize_amount.quantize(
                    Decimal("0.01")
                )  # Assure deux décimales
                logger.debug(
                    f"Calculé prize_amount: {prize_amount} ISK pour le gagnant: {random_ticket.user.username}"
                )
                winner = Winner.objects.create(
                    character=random_ticket.character,
                    ticket=random_ticket,
                    prize_amount=prize_amount,
                )
                winners.append(winner)
                logger.info(
                    f"Gagnant créé: {winner.ticket.user.username} - {winner.prize_amount} ISK"
                )

        return winners

    def notify_discord(self, winners):
        if not winners:
            # Ne rien faire ici, la notification est gérée par le signal
            logger.info(
                f"Aucun gagnant à notifier pour la loterie {self.lottery_reference}."
            )
            return

        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=self.payment_receiver
            )
            corp_name = corporation.corporation_name
        except EveCorporationInfo.DoesNotExist:
            corp_name = "Corporation Inconnue"

        # Import local pour éviter l'import circulaire
        # fortunaisk
        from fortunaisk.notifications import send_discord_notification

        for winner in winners:
            embed = {
                "title": "🎉🎉 **Félicitations au Gagnant!** 🎉🎉",
                "description": f"Nous sommes ravis d'annoncer que **{winner.character.character_name}** a remporté la loterie **{self.lottery_reference}** ! 🏆🥳",
                "color": 0xFFD700,  # Or
                "thumbnail": {
                    "url": "https://static.vecteezy.com/system/resources/previews/008/505/855/non_2x/banknotes-rain-illustration-money-falling-png.png"  # Image de trophée
                },
                "fields": [
                    {
                        "name": "🏆 **Utilisateur**",
                        "value": f"{winner.ticket.user.username}",
                        "inline": True,
                    },
                    {
                        "name": "🛡️ **Personnage**",
                        "value": f"{winner.character.character_name}",
                        "inline": True,
                    },
                    {
                        "name": "💰 **Prix**",
                        "value": f"💰 **{winner.prize_amount:,.2f} ISK**",
                        "inline": True,
                    },
                    {
                        "name": "📅 **Date de Gain**",
                        "value": f"{winner.won_at.strftime('%Y-%m-%d %H:%M')}",
                        "inline": False,
                    },
                    {
                        "name": "🔑 **Récepteur de Paiement**",
                        "value": corp_name,
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "Bonne chance à tous! 🍀",
                    "icon_url": "https://media.istockphoto.com/id/505920740/fr/vectoriel/bonne-chance.jpg?s=612x612&w=0&k=20&c=_woE0-ItyfRZ2o-wXbe3N1TYqPhxxvTzBHPZkRdP7qw=",  # Icône du footer
                },
                "timestamp": winner.won_at.isoformat(),
            }
            send_discord_notification(embed=embed)

    @property
    def participant_count(self):
        """Retourne le nombre de participants dans la loterie."""
        return self.ticket_purchases.count()


@receiver(post_save, sender=TicketPurchase)
def update_total_pot_on_ticket_purchase(sender, instance, created, **kwargs):
    if created:
        lottery = instance.lottery
        logger.debug(
            f"Signal post_save: Création de TicketPurchase pour la loterie {lottery.lottery_reference}"
        )
        lottery.update_total_pot()
        logger.info(
            f"Signal post_save: Total pot mis à jour pour la loterie {lottery.lottery_reference} après achat de ticket."
        )


@receiver(post_delete, sender=TicketPurchase)
def update_total_pot_on_ticket_delete(sender, instance, **kwargs):
    lottery = instance.lottery
    lottery.update_total_pot()
    logger.info(
        f"Signal post_delete: Total pot mis à jour pour la loterie {lottery.lottery_reference} après suppression de ticket."
    )
