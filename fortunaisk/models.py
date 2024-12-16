# Django
from django.db import models
from django.utils import timezone
from django.utils.timezone import now  # Import the `now` function

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
        default_permissions = ("add", "change", "delete")  # Supprime `view` auto-généré
        permissions = [
            ("view_ticket_custom", "Can view tickets (custom permission)"),
            ("admin", "Can manage Fortunaisk tickets"),
        ]

    def __str__(self):
        return f"{self.character} - {self.ticket_ref}"


class Config(models.Model):
    ticket_price = models.DecimalField(
        max_digits=10, decimal_places=0, default=100000000, verbose_name="Ticket Price"
    )
    next_draw_date = models.DateTimeField(
        default=now, verbose_name="Next Draw Date"  # Use `now` for the default value
    )

    def __str__(self):
        return "Configuration"

    class Meta:
        verbose_name = "Configuration"
        verbose_name_plural = "Configuration"


class Winner(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ("add", "change", "delete")  # Supprime `view` auto-généré
        permissions = [
            ("view_winner_custom", "Can view winners (custom permission)"),
            ("admin", "Can manage Fortunaisk winners"),
        ]

    def __str__(self):
        return f"Winner: {self.character} - {self.ticket.ticket_ref}"


class FortunaISKSettings(models.Model):
    ticket_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100.00,
        help_text="Price of a single ticket.",
    )
    next_drawing_date = models.DateTimeField(
        help_text="Date and time of the next automatic drawing."
    )

    def __str__(self):
        return "FortunaISK Settings"

    class Meta:
        verbose_name = "FortunaISK Setting"
        verbose_name_plural = "FortunaISK Settings"
