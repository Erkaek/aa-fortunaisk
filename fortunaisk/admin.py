# fortunaisk/admin.py
"""Configuration de l'administration Django pour l'application FortunaIsk."""

# Standard Library
import logging

# Django
from django.contrib import admin

from .models import Lottery, LotterySettings, TicketAnomaly, WebhookConfiguration
from .notifications import send_discord_webhook  # Import depuis notifications.py

logger = logging.getLogger(__name__)


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lottery_reference",
        "status",
        "participant_count",
        "total_pot",
    )
    search_fields = ("lottery_reference",)
    actions = ["mark_completed", "mark_cancelled"]
    readonly_fields = (
        "id",
        "lottery_reference",
        "status",
        "start_date",
        "participant_count",
        "total_pot",
    )
    fields = (
        "ticket_price",
        "start_date",
        "end_date",
        "payment_receiver",
        "lottery_reference",
        "status",
        "winner_count",
        "winners_distribution_str",
        "max_tickets_per_user",
        "participant_count",
        "total_pot",
    )

    def get_changeform_initial_data(self, request):
        settings = LotterySettings.objects.get_or_create()[0]
        return {"payment_receiver": settings.default_payment_receiver}

    def save_model(self, request, obj, form, change):
        """
        Override save_model to send a Discord notification when a lottery is created.
        """
        is_new = not change  # Check if this is a new object
        super().save_model(request, obj, form, change)

        if is_new:  # Only send notification for new lotteries
            message = (
                f":tada: Une nouvelle loterie a été créée !\n"
                f"**Référence :** {obj.lottery_reference}\n"
                f"**Prix du ticket :** {obj.ticket_price} ISK\n"
                f"**Date de fin :** {obj.end_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"**Récepteur des paiements :** {obj.payment_receiver}"
            )
            send_discord_webhook(message)

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        for lottery in queryset.filter(status="active"):
            lottery.status = "completed"
            lottery.save()
            self.message_user(
                request, f"{lottery.lottery_reference} marked as completed."
            )

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled")
        self.message_user(request, "Selected lotteries marked as cancelled.")


@admin.register(TicketAnomaly)
class TicketAnomalyAdmin(admin.ModelAdmin):
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


@admin.register(WebhookConfiguration)
class WebhookConfigurationAdmin(admin.ModelAdmin):
    list_display = ("webhook_url",)
    fields = ("webhook_url",)

    def has_add_permission(self, request):
        if WebhookConfiguration.objects.exists():
            return False
        return super().has_add_permission(request)
