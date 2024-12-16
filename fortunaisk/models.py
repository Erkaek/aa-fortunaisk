# Django
from django.db import models
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter


class Ticket(models.Model):
    character = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="tickets"
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    ticket_ref = models.CharField(max_length=72, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    paid = models.BooleanField(default=False)

    class Meta:
        default_permissions = ("add", "change", "delete")
        permissions = [
            ("view_ticket_custom", "Can view tickets (custom permission)"),
            ("admin", "Can manage Fortunaisk tickets"),
        ]

    def __str__(self):
        return f"{self.character} - {self.ticket_ref}"


class Winner(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ("add", "change", "delete")
        permissions = [
            ("view_winner_custom", "Can view winners (custom permission)"),
            ("admin", "Can manage Fortunaisk winners"),
        ]

    def __str__(self):
        return f"Winner: {self.character} - {self.ticket.ticket_ref}"


class FortunaISKSettings(models.Model):
    ticket_price = models.PositiveBigIntegerField(
        default=10000000, help_text="Price of a single ticket (in ISK)."
    )
    next_drawing_date = models.DateTimeField(
        help_text="Date and time of the next automatic drawing."
    )
    payment_receiver = models.CharField(
        max_length=100,
        default="Default Receiver",
        help_text="Name of the character or corporation to whom ISK should be sent.",
    )
    lottery_reference = models.CharField(
        max_length=50,
        unique=True,
        blank=True,  # Permet de ne pas remplir manuellement
        help_text="Unique reference for the current lottery.",
    )

    def save(self, *args, **kwargs):
        # Générer une référence unique seulement si elle est vide
        if not self.lottery_reference:
            self.lottery_reference = (
                f"LOTTERY-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return "FortunaISK Settings"
