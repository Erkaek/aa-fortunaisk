# Django
from django.contrib import admin

from .models import FortunaISKSettings, TicketPurchase, Winner


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "lottery_reference", "amount", "date")
    list_filter = ("lottery_reference", "date")
    search_fields = ("user__username", "character__character_name", "lottery_reference")


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
