# fortunaisk/admin.py
"""Configuration de l'administration Django pour l'application FortunaIsk."""

# Standard Library
import csv
import logging

# Django
from django.contrib import admin
from django.http import HttpResponse

from .models import Lottery, Reward, TicketAnomaly, UserProfile
from .webhooks import WebhookConfiguration  # Import depuis webhooks.py

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
    actions = ["mark_completed", "mark_cancelled", "export_as_csv", "terminate_lottery"]
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

    def has_add_permission(self, request):
        # Empêche l'ajout de nouvelles loteries via l'admin
        return False

    def save_model(self, request, obj, form, change):
        """
        Override save_model pour envoyer une notification Discord lorsque une loterie est mise à jour.
        """
        if change:
            try:
                old_obj = Lottery.objects.get(pk=obj.pk)
            except Lottery.DoesNotExist:
                old_obj = None

        super().save_model(request, obj, form, change)

        if change and old_obj:
            if old_obj.status != obj.status:
                if obj.status == "completed":
                    message = f"Loterie {obj.lottery_reference} terminée."
                elif obj.status == "cancelled":
                    message = f"Loterie {obj.lottery_reference} annulée."
                else:
                    message = f"Loterie {obj.lottery_reference} mise à jour."
                from .notifications import send_discord_notification  # Import interne

                send_discord_notification(message=message)

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        for lottery in queryset.filter(status="active"):
            lottery.status = "completed"
            lottery.save()
            self.message_user(
                request, f"{lottery.lottery_reference} marked as completed."
            )
            # Notifications Discord
            message = (
                f"Loterie {lottery.lottery_reference} a été marquée comme terminée."
            )
            from .notifications import send_discord_notification  # Import interne

            send_discord_notification(message=message)

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled")
        self.message_user(request, "Selected lotteries marked as cancelled.")
        # Notifications Discord
        message = "Les loteries sélectionnées ont été annulées."
        from .notifications import send_discord_notification  # Import interne

        send_discord_notification(message=message)

    @admin.action(description="Terminer prématurément les loteries sélectionnées")
    def terminate_lottery(self, request, queryset):
        for lottery in queryset.filter(status="active"):
            lottery.status = "completed"
            lottery.save()
            self.message_user(
                request, f"Loterie {lottery.lottery_reference} terminée prématurément."
            )
            # Notifications Discord
            message = f"Loterie {lottery.lottery_reference} a été terminée prématurément par {request.user.username}."
            from .notifications import send_discord_notification  # Import interne

            send_discord_notification(message=message)

    @admin.action(description="Exporter les loteries sélectionnées en CSV")
    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=lotteries.csv"
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response


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
    actions = ["export_anomalies_as_csv"]

    @admin.action(description="Exporter les anomalies sélectionnées en CSV")
    def export_anomalies_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = [field.name for field in meta.fields]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename=anomalies.csv"
        writer = csv.writer(response)

        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response


@admin.register(WebhookConfiguration)
class WebhookConfigurationAdmin(admin.ModelAdmin):
    list_display = ("webhook_url",)
    fields = ("webhook_url",)

    def has_add_permission(self, request):
        if WebhookConfiguration.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("name", "points_required")
    search_fields = ("name",)
    fields = ("name", "description", "points_required")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "points")
    search_fields = ("user__username",)
    fields = ("user", "points", "rewards")
