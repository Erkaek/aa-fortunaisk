# fortunaisk/admin.py
"""Django admin configuration for the FortunaIsk lottery application."""

# Django
from django.contrib import admin
from django.utils import timezone

from .models import Lottery, LotterySettings, TicketAnomaly, TicketPurchase


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    """
    Admin interface for the Lottery model.
    Only allows editing essential fields during creation:
    - ticket_price
    - end_date
    - payment_receiver (prefilled)
    start_date is automatically set to now and winner is read-only.
    """

    list_display = ("id", "lottery_reference", "winner_name_display", "status")
    search_fields = ("lottery_reference", "winner__username")
    actions = ["mark_completed", "mark_cancelled"]
    readonly_fields = ("id", "lottery_reference", "status", "start_date", "winner")
    fields = (
        "ticket_price",
        "start_date",
        "end_date",
        "payment_receiver",
        "lottery_reference",
        "status",
        "winner",
    )

    def get_changeform_initial_data(self, request):
        """
        Prefill the 'payment_receiver' field with the default value from LotterySettings.
        """
        settings = LotterySettings.objects.get_or_create()[0]
        return {"payment_receiver": settings.default_payment_receiver}

    def save_model(self, request, obj, form, change):
        """
        Automatically generate 'lottery_reference' if it does not exist on save.
        Automatically set 'start_date' if this is a new object.
        """
        if not change:
            # Set the start_date only on creation if not already set
            if not obj.start_date:
                obj.start_date = timezone.now()
        if not obj.lottery_reference:
            obj.lottery_reference = obj.generate_unique_reference()
        super().save_model(request, obj, form, change)

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        """
        Mark selected active lotteries as completed and randomly choose a winner if available.
        """
        for lottery in queryset.filter(status="active"):
            ticket = (
                TicketPurchase.objects.filter(lottery=lottery).order_by("?").first()
            )
            if ticket:
                lottery.winner = ticket.user
                lottery.status = "completed"
                lottery.save()
                self.message_user(
                    request, f"{lottery.lottery_reference} marked as completed."
                )
            else:
                self.message_user(
                    request,
                    f"No tickets found for {lottery.lottery_reference}.",
                    level="warning",
                )

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        """
        Mark selected lotteries as cancelled and remove the winner.
        """
        queryset.update(status="cancelled", winner=None)
        self.message_user(request, "Selected lotteries marked as cancelled.")

    @admin.display(description="Winner Name")
    def winner_name_display(self, obj):
        return obj.winner.username if obj.winner else "No winner yet"


@admin.register(TicketAnomaly)
class TicketAnomalyAdmin(admin.ModelAdmin):
    """
    Admin interface to view ticket anomalies.
    """

    list_display = (
        "lottery",
        "user",
        "character",
        "reason",
        "payment_date",
        "recorded_at",
    )
    search_fields = (
        "lottery__lottery_reference",
        "reason",
        "user__username",
        "character__character_name",
    )
    readonly_fields = (
        "lottery",
        "character",
        "user",
        "reason",
        "payment_date",
        "amount",
        "recorded_at",
    )
    fields = (
        "lottery",
        "character",
        "user",
        "reason",
        "payment_date",
        "amount",
        "recorded_at",
    )
