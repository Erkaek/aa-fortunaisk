# Standard Library
import ast
import csv

# Django
from django import forms
from django.contrib import admin
from django.db import models
from django.http import HttpResponse

# Alliance Auth
from allianceauth.services.hooks import get_extension_logger

from .models import AutoLottery, Lottery, TicketAnomaly, Winner, WinnerDistribution
from .models.webhook import WebhookConfiguration
from .notifications import notify_alliance as send_alliance_auth_notification
from .notifications import notify_discord_or_fallback

logger = get_extension_logger(__name__)


EVENT_CHOICES = [
    ("lottery_created", "Lottery Created"),
    ("lottery_sales_closed", "Lottery Sales Closed"),
    ("lottery_completed", "Lottery Completed"),
    ("lottery_cancelled", "Lottery Cancelled"),
    ("autolottery_activated", "AutoLottery Activated"),
    ("autolottery_paused", "AutoLottery Paused"),
    ("autolottery_suppressed", "AutoLottery Suppressed"),
    ("anomaly_detected", "Anomaly Detected"),
    ("anomaly_resolved", "Anomaly Resolved"),
    ("prize_distributed", "Prize Distributed"),
    ("reminder_24h_before_closure", "24h Before Closure Reminder"),
]


class ExportCSVMixin:
    """
    Mixin that adds CSV export capability to an admin class.
    Provides a customizable action for exporting selected objects to CSV format.
    """

    export_fields = []

    @admin.action(description="Export selected as CSV")
    def export_as_csv(self, request, queryset):
        """
        Action to export selected objects as CSV file.

        Args:
            request: The current HTTP request
            queryset: The queryset of selected objects

        Returns:
            HttpResponse containing CSV data
        """
        meta = self.model._meta
        fields = self.export_fields or [f.name for f in meta.fields]
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = (
            f'attachment; filename="{meta.verbose_name_plural}.csv"'
        )
        writer = csv.writer(resp)
        writer.writerow(fields)
        for obj in queryset:
            row = []
            for name in fields:
                val = getattr(obj, name)
                row.append(str(val) if isinstance(val, models.Model) else val)
            writer.writerow(row)
        return resp


class FortunaiskModelAdmin(admin.ModelAdmin):
    """
    Base ModelAdmin class for FortunaISK models.

    Enforces permission rules based on the can_admin_app permission.
    All admin views inherit from this class to ensure consistent permission handling.
    """

    def has_module_permission(self, request):
        """
        Check if user has permission to access this module.

        Args:
            request: The current HTTP request

        Returns:
            Boolean indicating permission access
        """
        return (
            request.user.has_perm("fortunaisk.can_admin_app")
            or request.user.is_superuser
        )

    def has_view_permission(self, request, obj=None):
        """
        Check if user has permission to view objects.

        Args:
            request: The current HTTP request
            obj: The object being viewed (optional)

        Returns:
            Boolean indicating permission access
        """
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        """
        Check if user has permission to add objects.

        Args:
            request: The current HTTP request

        Returns:
            Boolean indicating permission access
        """
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        """
        Check if user has permission to change objects.

        Args:
            request: The current HTTP request
            obj: The object being changed (optional)

        Returns:
            Boolean indicating permission access
        """
        return self.has_module_permission(request)

    def has_delete_permission(self, request, obj=None):
        """
        Check if user has permission to delete objects.

        Args:
            request: The current HTTP request
            obj: The object being deleted (optional)

        Returns:
            Boolean indicating permission access
        """
        return self.has_module_permission(request)


class WebhookConfigurationForm(forms.ModelForm):
    """
    Form for the WebhookConfiguration model.

    Handles special fields like notification_config (MultipleChoiceField)
    and ping_roles (CSV string of role IDs).
    """

    notification_config = forms.MultipleChoiceField(
        choices=EVENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Events to Notify",
        help_text="Which events should this webhook receive?",
    )
    ping_roles = forms.CharField(
        required=False,
        label="Ping Role IDs",
        help_text="Comma-separated Discord role IDs (no brackets).",
        widget=forms.TextInput(attrs={"placeholder": "12345,67890"}),
    )

    class Meta:
        model = WebhookConfiguration
        fields = ("name", "webhook_url", "notification_config", "ping_roles")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize the display values
        if self.instance and self.instance.notification_config:
            self.fields["notification_config"].initial = (
                self.instance.notification_config
            )
        if self.instance and self.instance.ping_roles:
            # Simple join for display purposes
            self.fields["ping_roles"].initial = ",".join(self.instance.ping_roles)

    def clean_notification_config(self):
        """
        Clean and validate notification_config field.

        Returns:
            List of selected notification events
        """
        return self.cleaned_data["notification_config"]

    def clean_ping_roles(self):
        """
        Clean and validate ping_roles field.

        Handles multiple input formats:
        1. List/tuple (flattens nested lists)
        2. String in Python list format (uses ast.literal_eval)
        3. Comma-separated values

        Returns:
            List of role IDs as strings
        """
        raw = self.cleaned_data.get("ping_roles", "")

        # 1) If already a list/tuple, flatten it
        if isinstance(raw, (list, tuple)):
            flat = []
            for item in raw:
                if isinstance(item, (list, tuple)):
                    flat.extend(str(x) for x in item)
                else:
                    flat.append(str(item))
            return [r.strip() for r in flat if r.strip()]

        # 2) If string in Python list format, use literal_eval
        if isinstance(raw, str):
            s = raw.strip()
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = ast.literal_eval(s)
                    if isinstance(parsed, (list, tuple)):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            # 3) Otherwise standard CSV
            return [r.strip() for r in s.split(",") if r.strip()]

        # 4) Empty fallback
        return []


@admin.register(WebhookConfiguration)
class WebhookConfigurationAdmin(ExportCSVMixin, FortunaiskModelAdmin):
    """
    Admin interface for WebhookConfiguration model.

    Handles display and validation of webhook configuration,
    including notification events and role pings.
    """

    form = WebhookConfigurationForm
    list_display = (
        "name",
        "webhook_url",
        "notification_config_display",
        "ping_roles_display",
        "created_at",
        "created_by",
    )
    fields = (
        "name",
        "webhook_url",
        "notification_config",
        "ping_roles",
        "created_at",
        "created_by",
    )
    readonly_fields = ("created_at", "created_by")
    export_fields = list_display

    def save_model(self, request, obj, form, change):
        """
        Custom save method to capture user who created the webhook.

        Args:
            request: The current HTTP request
            obj: The object being saved
            form: The form instance
            change: Boolean indicating if this is a change operation
        """
        if not change:
            obj.created_by = request.user
        # notification_config and ping_roles are already clean lists
        super().save_model(request, obj, form, change)

    @admin.display(description="Events")
    def notification_config_display(self, obj):
        """
        Format notification_config for display in list view.

        Args:
            obj: WebhookConfiguration instance

        Returns:
            String representation of notification events
        """
        return ", ".join(obj.notification_config or [])

    @admin.display(description="Ping Roles")
    def ping_roles_display(self, obj):
        """
        Format ping_roles for display in list view.

        Args:
            obj: WebhookConfiguration instance

        Returns:
            String representation of role IDs
        """
        roles = obj.ping_roles

        # If not already a list/tuple, try to interpret
        if not isinstance(roles, (list, tuple)):
            # If it's a string, try literal_eval to get a list
            if isinstance(roles, str):
                # Standard Library
                import ast

                try:
                    parsed = ast.literal_eval(roles)
                    if isinstance(parsed, (list, tuple)):
                        roles = parsed
                    else:
                        # It wasn't a list → show raw
                        return roles
                except Exception:
                    return roles
            else:
                # Neither str nor list → show nothing
                return ""

        # Now we properly have a list/tuple
        return ", ".join(str(x) for x in roles)


@admin.register(Lottery)
class LotteryAdmin(ExportCSVMixin, FortunaiskModelAdmin):
    """
    Admin interface for Lottery model.

    Provides actions for managing lotteries, including completing and canceling.
    """

    list_display = (
        "id",
        "lottery_reference",
        "status",
        "participant_count",
        "total_pot",
    )
    search_fields = ("lottery_reference",)
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
        "tax",
        "duration_value",
        "duration_unit",
        "winner_count",
        "max_tickets_per_user",
        "payment_receiver",
        "lottery_reference",
        "status",
        "participant_count",
        "total_pot",
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
        "tax",
        "duration_value",
        "duration_unit",
        "winner_count",
        "max_tickets_per_user",
        "payment_receiver",
    ]
    actions = ["mark_completed", "mark_cancelled", "terminate_lottery", "export_as_csv"]

    def has_add_permission(self, request):
        """
        Override to disable direct creation through admin interface.

        Args:
            request: The current HTTP request

        Returns:
            False to disable creation
        """
        return False

    @admin.display(description="Number of Participants")
    def participant_count(self, obj):
        """
        Calculate the number of participants for display.

        Args:
            obj: Lottery instance

        Returns:
            Count of ticket purchases
        """
        return obj.ticket_purchases.count()

    @admin.action(description="Mark selected as completed")
    def mark_completed(self, request, queryset):
        """
        Action to mark selected lotteries as completed.

        Args:
            request: The current HTTP request
            queryset: Selected lotteries
        """
        count = 0
        for lot in queryset.filter(status="active"):
            lot.complete_lottery()
            count += 1
        self.message_user(request, f"{count} lotteries completed.")
        notify_discord_or_fallback(
            users=[],
            event="lottery_completed",
            message=f"{count} lotteries completed by {request.user.username}.",
            private=False,
        )
        send_alliance_auth_notification(
            request.user, "Lotteries Completed", f"{count} lotteries completed."
        )

    @admin.action(description="Mark selected as cancelled")
    def mark_cancelled(self, request, queryset):
        """
        Action to mark selected lotteries as cancelled.

        Args:
            request: The current HTTP request
            queryset: Selected lotteries
        """
        count = queryset.filter(status="active").update(status="cancelled")
        self.message_user(request, f"{count} lotteries cancelled.")
        notify_discord_or_fallback(
            users=[],
            event="lottery_cancelled",
            message=f"{count} lotteries cancelled by {request.user.username}.",
            private=False,
        )
        send_alliance_auth_notification(
            request.user, "Lotteries Cancelled", f"{count} lotteries cancelled."
        )

    @admin.action(description="Terminate selected prematurely")
    def terminate_lottery(self, request, queryset):
        """
        Action to terminate selected lotteries prematurely.

        Args:
            request: The current HTTP request
            queryset: Selected lotteries
        """
        count = 0
        for lot in queryset.filter(status="active"):
            lot.status = "cancelled"
            lot.save(update_fields=["status"])
            count += 1
        self.message_user(request, f"{count} lotteries terminated prematurely.")
        notify_discord_or_fallback(
            users=[],
            event="lottery_cancelled",
            message=f"{count} lotteries terminated by {request.user.username}.",
            private=False,
        )
        send_alliance_auth_notification(
            request.user, "Lotteries Terminated", f"{count} lotteries terminated."
        )


@admin.register(TicketAnomaly)
class TicketAnomalyAdmin(ExportCSVMixin, FortunaiskModelAdmin):
    """
    Admin interface for TicketAnomaly model.

    Provides read-only access to anomalies for auditing purposes.
    """

    list_display = (
        "lottery",
        "user",
        "character",
        "reason",
        "amount",
        "payment_date",
        "recorded_at",
        "solved",
        "solved_at",
        "solved_by",
    )
    search_fields = (
        "lottery__lottery_reference",
        "reason",
        "user__username",
        "character__character_name",
    )
    readonly_fields = (
        "lottery",
        "user",
        "character",
        "reason",
        "amount",
        "payment_date",
        "recorded_at",
        "payment_id",
        "solved",
        "solved_at",
        "solved_by",
        "detail",
    )
    fields = (
        "lottery",
        "user",
        "character",
        "reason",
        "amount",
        "payment_date",
        "payment_id",
        "recorded_at",
    )
    actions = ["export_as_csv"]


@admin.register(AutoLottery)
class AutoLotteryAdmin(ExportCSVMixin, FortunaiskModelAdmin):
    """
    Admin interface for AutoLottery model.

    Manages automatic lottery configurations.
    """

    list_display = (
        "id",
        "name",
        "is_active",
        "frequency",
        "frequency_unit",
        "ticket_price",
        "tax",
        "duration_value",
        "duration_unit",
        "winner_count",
        "max_tickets_per_user",
    )
    search_fields = ("name",)
    fields = (
        "is_active",
        "name",
        "frequency",
        "frequency_unit",
        "ticket_price",
        "tax",
        "duration_value",
        "duration_unit",
        "winner_count",
        "winners_distribution",
        "payment_receiver",
        "max_tickets_per_user",
    )
    export_fields = list_display
    actions = ["export_as_csv"]


@admin.register(Winner)
class WinnerAdmin(FortunaiskModelAdmin):
    """
    Admin interface for Winner model.

    Manages lottery winners and prize distribution status.
    """

    list_display = (
        "id",
        "ticket",
        "character",
        "prize_amount",
        "won_at",
        "distributed",
        "distributed_at",
        "distributed_by",
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
        "distributed_at",
        "distributed_by",
    )
    fields = (
        "ticket",
        "character",
        "prize_amount",
        "won_at",
        "distributed",
        "distributed_at",
        "distributed_by",
    )
    list_filter = ("distributed",)

    @admin.action(description="Mark selected prizes distributed")
    def mark_as_distributed(self, request, queryset):
        """
        Action to mark selected prizes as distributed.

        Args:
            request: The current HTTP request
            queryset: Selected winners
        """
        count = queryset.filter(distributed=False).update(distributed=True)
        self.message_user(request, f"{count} prizes marked as distributed.")
        notify_discord_or_fallback(
            users=[],
            event="prize_distributed",
            message=f"{count} prizes distributed by {request.user.username}.",
            private=False,
        )
        send_alliance_auth_notification(
            request.user, "Prizes Distributed", f"{count} prizes distributed."
        )


@admin.register(WinnerDistribution)
class WinnerDistributionAdmin(FortunaiskModelAdmin):
    """
    Admin interface for WinnerDistribution model.

    Manages lottery prize distribution configurations.
    """

    list_display = (
        "lottery_reference",
        "winner_rank",
        "winner_prize_distribution",
        "created_at",
        "updated_at",
    )
    list_filter = ("lottery_reference",)
    search_fields = ("lottery_reference",)
    readonly_fields = ("created_at", "updated_at")
