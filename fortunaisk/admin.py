# Django
from django.contrib import admin
from django.utils import timezone

from .models import FortunaISKSettings, Lottery, TicketPurchase, Winner


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = ("lottery_reference", "is_active", "winner", "next_drawing_date")
    search_fields = ("lottery_reference", "winner__username")
    actions = ["mark_completed", "mark_cancelled"]

    @admin.action(description="Marquer les loteries sélectionnées comme complétées")
    def mark_completed(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "Loteries marquées comme complétées.")

    @admin.action(description="Marquer les loteries sélectionnées comme annulées")
    def mark_cancelled(self, request, queryset):
        queryset.update(is_active=False, winner=None)
        self.message_user(request, "Loteries marquées comme annulées.")


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "lottery", "amount", "date")


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

    # Vérifiez si ce modèle est utilisé dans les vues
    # Sinon, envisagez de le supprimer pour éviter les redondances
