# Django
from django.contrib import admin

from .models import FortunaISKSettings, Lottery, TicketPurchase, Winner


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = ("lottery_reference", "is_active", "winner", "next_drawing_date")
    search_fields = ("lottery_reference", "winner_name")
    actions = ["mark_completed", "mark_cancelled"]

    @admin.action(description="Marquer les loteries sélectionnées comme complétées")
    def mark_completed(self, request, queryset):
        queryset.update(status="completed")
        self.message_user(request, "Loteries marquées comme complétées.")

    @admin.action(description="Marquer les loteries sélectionnées comme annulées")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled", winner_name=None)
        self.message_user(request, "Loteries marquées comme annulées.")


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "lottery", "amount", "date")
    search_fields = ("user__username", "character__name")


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
    search_fields = ("lottery_reference", "payment_receiver")
