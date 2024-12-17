# fortunaisk/admin.py

# Django
from django.contrib import admin
from django.utils import timezone

from .models import FortunaISKSettings, Lottery, TicketPurchase, Winner


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = (
        "lottery_reference",
        "ticket_price",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("lottery_reference", "payment_receiver")
    ordering = ("-start_date",)
    readonly_fields = ("lottery_reference",)

    actions = ["complete_lottery", "cancel_lottery"]

    @admin.action(description="Mark selected lotteries as completed")
    def complete_lottery(self, request, queryset):
        updated = queryset.update(status="completed", end_date=timezone.now())
        self.message_user(request, f"{updated} lottery(ies) marked as completed.")

    @admin.action(description="Cancel selected lotteries")
    def cancel_lottery(self, request, queryset):
        updated = queryset.update(status="cancelled", end_date=timezone.now())
        self.message_user(request, f"{updated} lottery(ies) cancelled.")


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "lottery", "amount", "date")
    list_filter = ("lottery", "date")
    search_fields = (
        "user__username",
        "character__character_name",
        "lottery__lottery_reference",
    )
    ordering = ("-date",)
    list_select_related = ("user", "character", "lottery")


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ("character", "ticket", "won_at")
    ordering = ("-won_at",)
    list_select_related = ("character", "ticket")


@admin.register(FortunaISKSettings)
class FortunaISKSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_price",
        "next_drawing_date",
        "payment_receiver",
        "lottery_reference",
    )
    readonly_fields = ("lottery_reference",)
    ordering = ("-next_drawing_date",)
