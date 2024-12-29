# fortunaisk/admin.py

# Standard Library
import csv
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from solo.admin import SingletonModelAdmin

# Django
from django.contrib import admin
from django.db import models
from django.http import HttpResponse

from .models import (
    AuditLog,
    AutoLottery,
    Lottery,
    TicketAnomaly,
    WebhookConfiguration,
    Winner,
)
from .notifications import send_alliance_auth_notification, send_discord_notification

logger = logging.getLogger(__name__)


class ExportCSVMixin:
    export_fields = []

    @admin.action(description="Export selected items to CSV")
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
            row = []
            for field in field_names:
                value = getattr(obj, field)
                if isinstance(value, models.Model):
                    value = str(value)
                row.append(value)
            writer.writerow(row)

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
    actions = [
        "mark_completed",
        "mark_cancelled",
        "export_as_csv",
        "terminate_lottery",
    ]
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
        # Nous n'autorisons pas la création via l'admin pour les loteries standards
        return False

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

                send_alliance_auth_notification(
                    user=request.user,
                    title="Lottery Status Changed",
                    message=message,
                    level="info",
                )
                send_discord_notification(message=message)

    @admin.action(description="Mark selected lotteries as completed")
    def mark_completed(self, request, queryset):
        updated = 0
        for lottery in queryset.filter(status="active"):
            lottery.complete_lottery()
            updated += 1
        self.message_user(request, f"{updated} lottery(ies) marked as completed.")
        send_discord_notification(
            message=f"{updated} lottery(ies) have been completed."
        )
        send_alliance_auth_notification(
            user=request.user,
            title="Lotteries Completed",
            message=f"{updated} lottery(ies) have been completed.",
            level="info",
        )

    @admin.action(description="Mark selected lotteries as cancelled")
    def mark_cancelled(self, request, queryset):
        updated = queryset.filter(status="active").count()
        queryset.filter(status="active").update(status="cancelled")
        self.message_user(request, f"{updated} lottery(ies) cancelled.")
        send_discord_notification(
            message=f"{updated} lottery(ies) have been cancelled."
        )
        send_alliance_auth_notification(
            user=request.user,
            title="Lotteries Cancelled",
            message=f"{updated} lottery(ies) have been cancelled.",
            level="warning",
        )

    @admin.action(description="Terminate selected lotteries prematurely")
    def terminate_lottery(self, request, queryset):
        updated = 0
        for lottery in queryset.filter(status="active"):
            lottery.status = "cancelled"
            lottery.save(update_fields=["status"])
            updated += 1
        self.message_user(
            request,
            f"{updated} lottery(ies) terminated prematurely.",
        )
        send_discord_notification(
            message=f"{updated} lottery(ies) terminated prematurely by {request.user.username}."
        )
        send_alliance_auth_notification(
            user=request.user,
            title="Lotteries Terminated Prematurely",
            message=f"{updated} lottery(ies) terminated prematurely by {request.user.username}.",
            level="warning",
        )

    @admin.display(description="Number of Participants")
    def participant_count(self, obj):
        """
        Affiche le nombre de participants dans la loterie.
        """
        count = obj.ticket_purchases.count()
        return count


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
    actions = ["export_as_csv"]
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
    readonly_fields = ()
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
        "payment_receiver",
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
        "payment_receiver",
        "max_tickets_per_user",
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            if obj.is_active:
                message = f"AutoLottery {obj.name} is now active."

                # Définir la période basée sur la fréquence et l'unité
                if obj.frequency_unit == "minutes":
                    period = IntervalSchedule.MINUTES
                elif obj.frequency_unit == "hours":
                    period = IntervalSchedule.HOURS
                elif obj.frequency_unit == "days":
                    period = IntervalSchedule.DAYS
                else:
                    # fallback par défaut
                    period = IntervalSchedule.DAYS
                interval, created = IntervalSchedule.objects.get_or_create(
                    every=obj.frequency,
                    period=period,
                )

                task_name = f"create_lottery_from_autolottery_{obj.id}"
                PeriodicTask.objects.update_or_create(
                    name=task_name,
                    defaults={
                        "task": "fortunaisk.tasks.create_lottery_from_auto_lottery",
                        "interval": interval,
                        "args": json.dumps([obj.id]),
                    },
                )
                logger.info(
                    f"Periodic task '{task_name}' created/updated for AutoLottery {obj.id}."
                )
            else:
                message = f"AutoLottery {obj.name} has been deactivated."
                task_name = f"create_lottery_from_autolottery_{obj.id}"
                try:
                    task = PeriodicTask.objects.get(name=task_name)
                    task.delete()
                    logger.info(
                        f"Periodic task '{task_name}' deleted for AutoLottery {obj.id}."
                    )
                except PeriodicTask.DoesNotExist:
                    logger.warning(
                        f"Periodic task '{task_name}' does not exist for AutoLottery {obj.id}."
                    )

            send_discord_notification(message=message)
            send_alliance_auth_notification(
                user=request.user,
                title="AutoLottery Status Changed",
                message=message,
                level="info",
            )


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "ticket",
        "character",
        "prize_amount",
        "won_at",
        "distributed",
    )
    search_fields = (
        "ticket__user__username",
        "character__character_name",
        "ticket__lottery__lottery_reference",
    )
    readonly_fields = (
        "ticket",
        "character",
        "prize_amount",
        "won_at",
    )
    fields = (
        "ticket",
        "character",
        "prize_amount",
        "won_at",
        "distributed",
    )
    list_filter = ("distributed",)
    actions = ["mark_as_distributed"]

    @admin.action(description="Mark selected winnings as distributed")
    def mark_as_distributed(self, request, queryset):
        updated = queryset.filter(distributed=False).update(distributed=True)
        self.message_user(request, f"{updated} prize(s) marked as distributed.")
        send_discord_notification(
            message=f"{updated} prize(s) have been marked as distributed."
        )
        send_alliance_auth_notification(
            user=request.user,
            title="Prizes Distributed",
            message=f"{updated} prize(s) have been marked as distributed.",
            level="success",
        )


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

    def has_add_permission(self, request):
        if WebhookConfiguration.objects.exists():
            return False
        return True

    def has_change_permission(self, request, obj=None):
        return True


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action_type", "model", "object_id")
    list_filter = ("action_type", "model", "user")
    search_fields = ("user__username", "model", "object_id")
    readonly_fields = (
        "user",
        "action_type",
        "timestamp",
        "model",
        "object_id",
        "changes",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
