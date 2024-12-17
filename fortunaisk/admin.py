# Django
from django.contrib import admin

from .models import Lottery, TicketPurchase, Winner, LotterySettings


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = (
        "lottery_reference",
        "is_active",
        "winner_name",
        "next_drawing_date",
    )
    search_fields = ("lottery_reference", "winner_name")
    actions = ["mark_completed", "mark_cancelled"]
    readonly_fields = ("lottery_reference", "winner_name")

    def save_model(self, request, obj, form, change):
        if not obj.lottery_reference:
            obj.lottery_reference = f"LOTTERY-{obj.start_date.strftime('%Y%m%d')}-{obj.end_date.strftime('%Y%m%d')}"
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        for lottery in queryset.filter(status="active"):
            ticket = (
                TicketPurchase.objects.filter(lottery=lottery).order_by("?").first()
            )
            if ticket:
                lottery.winner_name = ticket.character.character_name
                lottery.status = "completed"
                lottery.save()
                self.message_user(
                    request, f"{lottery.lottery_reference} marked as completed."
                )
            else:
                self.message_user(
                    request,
                    f"No tickets for {lottery.lottery_reference}.",
                    level="warning",
                )

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled", winner_name=None)
        self.message_user(request, "Selected lotteries marked as cancelled.")


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "lottery", "amount", "date")
    search_fields = ("user__username", "character__character_name")


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ("character", "ticket", "won_at")
    readonly_fields = ("ticket", "character", "won_at")


@admin.register(LotterySettings)
class LotterySettingsAdmin(SingletonModelAdmin):
    list_display = ("default_payment_receiver",)
