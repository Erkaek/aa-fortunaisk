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
    readonly_fields = ("lottery_reference",)
    actions = ["mark_completed", "mark_cancelled"]

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        queryset.update(status="completed", end_date=timezone.now())

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled", end_date=timezone.now())


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
