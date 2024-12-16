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
    list_display = (
        "ticket_price",
        "next_drawing_date",
        "payment_receiver",
        "lottery_reference",
    )
    readonly_fields = ("lottery_reference",)
