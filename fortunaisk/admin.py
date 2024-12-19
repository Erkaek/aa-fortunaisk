# Django
from django.contrib import admin

from .models import Lottery, LotterySettings, TicketPurchase


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    """
    Admin interface for the Lottery model.
    """

    list_display = ("id", "lottery_reference", "winner_name_display", "status")
    search_fields = ("lottery_reference", "winner_name_display")
    actions = ["mark_completed", "mark_cancelled"]
    readonly_fields = ("id", "lottery_reference", "start_date", "end_date", "status")

    def get_changeform_initial_data(self, request):
        """
        Pré-remplir le champ 'payment_receiver' avec la valeur par défaut depuis LotterySettings.
        """
        settings = LotterySettings.objects.get_or_create()[
            0
        ]  # Récupère les paramètres globaux
        return {"payment_receiver": settings.default_payment_receiver}

    def save_model(self, request, obj, form, change):
        """
        Automatiquement générer 'lottery_reference' lors de la sauvegarde.
        """
        if not obj.lottery_reference:
            obj.lottery_reference = obj.generate_unique_reference()
        super().save_model(request, obj, form, change)

    @admin.display(description="Next Drawing Date")
    def get_next_drawing_date(self, obj):
        """
        Affiche la prochaine date de tirage.
        """
        return obj.next_drawing_date.strftime("%Y-%m-%d %H:%M")

    @admin.action(description="Marquer les loteries sélectionnées comme complétées")
    def mark_completed(self, request, queryset):
        """
        Marquer les loteries comme 'completed' et définir le gagnant.
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
                    f"No tickets for {lottery.lottery_reference}.",
                    level="warning",
                )

    @admin.action(description="Marquer les loteries sélectionnées comme annulées")
    def mark_cancelled(self, request, queryset):
        """
        Marquer les loteries comme 'cancelled' et retirer le gagnant.
        """
        queryset.update(status="cancelled", winner=None)
        self.message_user(request, "Selected lotteries marked as cancelled.")

    @admin.display(description="Winner Name")
    def winner_name_display(self, obj):
        return obj.winner.username if obj.winner else "No winner yet"
