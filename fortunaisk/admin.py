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
    TicketAnomaly,
    WebhookConfiguration,
    Winner,
)
from fortunaisk.notifications import (
    send_alliance_auth_notification,
    send_discord_notification,
)

logger = logging.getLogger(__name__)


class ExportCSVMixin:
    """
    Mixin pour ajouter une action d'exportation CSV dans ModelAdmin.
    """

    export_fields = []

    @admin.action(description="Exporter les éléments sélectionnés au format CSV")
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
        return False  # Désactiver la création via l'admin

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
                    message = f"Loterie {obj.lottery_reference} terminée."
                elif obj.status == "cancelled":
                    message = f"Loterie {obj.lottery_reference} annulée."
                else:
                    message = f"Loterie {obj.lottery_reference} mise à jour."

                # Envoyer une notification via Alliance Auth
                send_alliance_auth_notification(
                    event_type="lottery_status_changed",
                    user=request.user,
                    context={
                        "lottery_reference": obj.lottery_reference,
                        "new_status": obj.status,
                    },
                )

                # Envoyer une notification Discord
                send_discord_notification(message=message)

    @admin.action(description="Marquer les loteries sélectionnées comme terminées")
    def mark_completed(self, request, queryset):
        updated = 0
        for lottery in queryset.filter(status="active"):
            lottery.complete_lottery()
            updated += 1
        self.message_user(
            request, f"{updated} loterie(s) marquée(s) comme terminée(s)."
        )
        send_discord_notification(message=f"{updated} loterie(s) ont été terminée(s).")
        send_alliance_auth_notification(
            event_type="lotteries_marked_completed",
            user=request.user,
            context={"count": updated},
        )

    @admin.action(description="Marquer les loteries sélectionnées comme annulées")
    def mark_cancelled(self, request, queryset):
        updated = queryset.filter(status="active").update(status="cancelled")
        self.message_user(request, f"{updated} loterie(s) annulée(s).")
        send_discord_notification(message=f"{updated} loterie(s) ont été annulée(s).")
        send_alliance_auth_notification(
            event_type="lotteries_marked_cancelled",
            user=request.user,
            context={"count": updated},
        )

    @admin.action(description="Terminer prématurément les loteries sélectionnées")
    def terminate_lottery(self, request, queryset):
        updated = 0
        for lottery in queryset.filter(status="active"):
            lottery.complete_lottery()
            updated += 1
        self.message_user(request, f"{updated} loterie(s) terminée(s) prématurément.")
        send_discord_notification(
            message=f"{updated} loterie(s) ont été terminée(s) prématurément par {request.user.username}."
        )
        send_alliance_auth_notification(
            event_type="lotteries_terminated_prematurely",
            user=request.user,
            context={"count": updated, "admin": request.user.username},
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
                message = f"AutoLoterie {obj.name} est maintenant active."
            else:
                message = f"AutoLoterie {obj.name} a été désactivée."
            send_discord_notification(message=message)
            send_alliance_auth_notification(
                event_type="autolottery_status_changed",
                user=request.user,
                context={"autolottery_name": obj.name, "new_status": obj.is_active},
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

    @admin.action(description="Marquer les gains sélectionnés comme distribués")
    def mark_as_distributed(self, request, queryset):
        updated = queryset.filter(distributed=False).update(distributed=True)
        self.message_user(request, f"{updated} gain(s) marqué(s) comme distribués.")
        send_discord_notification(
            message=f"{updated} gain(s) ont été marqué(s) comme distribués."
        )
        send_alliance_auth_notification(
            event_type="prizes_marked_distributed",
            user=request.user,
            context={"count": updated},
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
