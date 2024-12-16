# admin.py
# Django
from django.contrib import admin

from .models import FortunaISKSettings, Ticket, Winner


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("character", "ticket_ref", "amount", "paid", "created_at")


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ("character", "ticket", "won_at")


@admin.register(FortunaISKSettings)
class FortunaISKSettingsAdmin(admin.ModelAdmin):
    list_display = ("ticket_price", "next_drawing_date")
    fieldsets = (
        (
            None,
            {
                "fields": ("ticket_price", "next_drawing_date"),
                "description": "Configure the ticket price and the date of the next automatic drawing.",
            },
        ),
    )

    def has_add_permission(self, request):
        # Prevent adding new settings; only allow editing the existing one.
        return not FortunaISKSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of the settings.
        return False
