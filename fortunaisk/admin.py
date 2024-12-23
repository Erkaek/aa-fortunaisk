# fortunaisk/admin.py
# Standard Library
import csv
import logging

# Third Party
from solo.admin import SingletonModelAdmin

# Django
from django.contrib import admin
from django.http import HttpResponse

# fortunaisk
from fortunaisk.models import (
    AutoLottery,
    Lottery,
    Reward,
    TicketAnomaly,
    UserProfile,
    WebhookConfiguration,
)
from fortunaisk.notifications import send_discord_notification

logger = logging.getLogger(__name__)


class ExportCSVMixin:
    """
    Mixin to add CSV export action in ModelAdmin.
    """

    export_fields = []

    @admin.action(description="Export selected as CSV")
    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        field_names = self.export_fields or [field.name for field in meta.fields]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f"attachment; filename={meta.verbose_name_plural}.csv"
        )
        writer = csv.writer(response)
        writer.writerow(field_names)
        for obj in queryset:
            writer.writerow([getattr(obj, field) for field in field_names])

        return response


@admin.register(Lottery)
class LotteryAdmin(ExportCSVMixin, admin.ModelAdmin):
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
        "end_date",
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
        "winners_distribution",
        "max_tickets_per_user",
        "participant_count",
        "total_pot",
        "duration_value",
        "duration_unit",
    )
    export_fields = [
        "id",
        "lottery_reference",
        "status",
        "start_date",
        "end_date",
        "participant_count",
        "total_pot",
        "ticket_price",
        "payment_receiver",
        "winner_count",
        "winners_distribution",
        "max_tickets_per_user",
        "duration_value",
        "duration_unit",
    ]

    def has_add_permission(self, request):
        return False  # disallow creation via admin

    def save_model(self, request, obj, form, change):
        if change:
            try:
                old_obj = Lottery.objects.get(pk=obj.pk)
            except Lottery.DoesNotExist:
                old_obj = None
        super().save_model(request, obj, form, change)

        if change and old_obj:
            if old_obj.status != obj.status:
                if obj.status == "completed":
                    message = f"Lottery {obj.lottery_reference} completed."
                elif obj.status == "cancelled":
                    message = f"Lottery {obj.lottery_reference} cancelled."
                else:
                    message = f"Lottery {obj.lottery_reference} updated."

                send_discord_notification(message=message)

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        updated = queryset.filter(status="active").update(status="completed")
        self.message_user(request, f"{updated} lottery(ies) marked as completed.")
        send_discord_notification(
            message=f"{updated} lottery(ies) have been completed."
        )

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        updated = queryset.update(status="cancelled")
        self.message_user(request, f"{updated} lottery(ies) cancelled.")
        send_discord_notification(
            message=f"{updated} lottery(ies) have been cancelled."
        )

    @admin.action(description="Terminate selected lotteries prematurely")
    def terminate_lottery(self, request, queryset):
        updated = queryset.filter(status="active").update(status="completed")
        self.message_user(request, f"{updated} lottery(ies) terminated prematurely.")
        send_discord_notification(
            message=f"{updated} lottery(ies) terminated prematurely by {request.user.username}."
        )


@admin.register(TicketAnomaly)
class TicketAnomalyAdmin(ExportCSVMixin, admin.ModelAdmin):
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
        "payment_id",
    )
    fields = (
        "lottery",
        "character",
        "user",
        "reason",
        "payment_date",
        "amount",
        "recorded_at",
        "payment_id",
    )
    actions = ["export_anomalies_as_csv"]
    export_fields = [
        "lottery",
        "user",
        "character",
        "reason",
        "payment_date",
        "amount",
        "recorded_at",
        "payment_id",
    ]

    @admin.action(description="Export selected anomalies as CSV")
    def export_anomalies_as_csv(self, request, queryset):
        return self.export_as_csv(request, queryset)


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = ("name", "points_required")
    search_fields = ("name",)
    fields = ("name", "description", "points_required")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user",)
    search_fields = ("user__username",)
    fields = ("user", "rewards")


@admin.register(AutoLottery)
class AutoLotteryAdmin(ExportCSVMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "is_active",
        "frequency",
        "frequency_unit",
        "ticket_price",
        "duration_value",
        "duration_unit",
        "winner_count",
        "max_tickets_per_user",
    )
    search_fields = ("name",)
    actions = ["export_as_csv"]
    readonly_fields = ("max_tickets_per_user",)
    fields = (
        "is_active",
        "name",
        "frequency",
        "frequency_unit",
        "ticket_price",
        "duration_value",
        "duration_unit",
        "winner_count",
        "winners_distribution",
        "max_tickets_per_user",
    )
    export_fields = [
        "id",
        "name",
        "is_active",
        "frequency",
        "frequency_unit",
        "ticket_price",
        "duration_value",
        "duration_unit",
        "winner_count",
        "winners_distribution",
        "max_tickets_per_user",
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            if obj.is_active:
                message = f"AutoLottery {obj.name} is now active."
            else:
                message = f"AutoLottery {obj.name} has been deactivated."
            send_discord_notification(message=message)


@admin.register(WebhookConfiguration)
class WebhookConfigurationAdmin(SingletonModelAdmin):
    fieldsets = (
        (
            None,
            {
                "fields": ("webhook_url",),
            },
        ),
    )
