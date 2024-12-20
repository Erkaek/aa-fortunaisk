# fortunaisk/admin.py
"""Django admin configuration for the FortunaIsk lottery application."""

# Django
from django.contrib import admin
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render
from django.utils import timezone

from .models import (
    Lottery,
    LotterySettings,
    TicketAnomaly,
    TicketPurchase,
    WebhookConfiguration,
)


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
        "winners_distribution",
        "max_tickets_per_user",
        "participant_count",
        "total_pot",
    )

    def get_changeform_initial_data(self, request):
        settings = LotterySettings.objects.get_or_create()[0]
        return {"payment_receiver": settings.default_payment_receiver}

    def save_model(self, request, obj, form, change):
        if not change:
            if not obj.start_date:
                obj.start_date = timezone.now()
        if not obj.lottery_reference:
            obj.lottery_reference = obj.generate_unique_reference()
        super().save_model(request, obj, form, change)

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


@login_required
@permission_required("fortunaisk.admin", raise_exception=True)
def admin_dashboard(request):
    active_lotteries = Lottery.objects.filter(status="active")
    anomalies = TicketAnomaly.objects.all()

    total_tickets = TicketPurchase.objects.count()
    total_lotteries = Lottery.objects.count()
    total_anomalies = anomalies.count()

    completed_lotteries = Lottery.objects.filter(status="completed")
    if completed_lotteries.exists():
        avg_participation = (
            sum(lot.participant_count for lot in completed_lotteries)
            / completed_lotteries.count()
        )
    else:
        avg_participation = 0

    lotteries = Lottery.objects.all().order_by("id")
    lottery_names = [lot.lottery_reference for lot in lotteries]
    tickets_per_lottery = [
        TicketPurchase.objects.filter(lottery=lot).count() for lot in lotteries
    ]
    total_pots = [lot.total_pot for lot in lotteries]

    stats = {
        "total_tickets": total_tickets,
        "total_lotteries": total_lotteries,
        "total_anomalies": total_anomalies,
        "avg_participation": avg_participation,
    }

    context = {
        "active_lotteries": active_lotteries,
        "anomalies": anomalies,
        "stats": stats,
        "lottery_names": lottery_names,
        "tickets_per_lottery": tickets_per_lottery,
        "total_pots": total_pots,
    }

    return render(request, "fortunaisk/admin.html", context)
