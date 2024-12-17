# Django
from django.contrib import admin

from .models import Lottery, LotterySettings, TicketPurchase, Winner


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = (
        "lottery_reference",
        "is_active",
        "winner_name",
        "get_next_drawing_date",  # Remplacer next_drawing_date par une méthode
    )
    search_fields = ("lottery_reference", "winner_name")
    actions = ["mark_completed", "mark_cancelled"]
    readonly_fields = ("lottery_reference", "winner_name")  # Champs en lecture seule

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
            obj.lottery_reference = f"LOTTERY-{obj.start_date.strftime('%Y%m%d')}-{obj.end_date.strftime('%Y%m%d')}"
        super().save_model(request, obj, form, change)

    @admin.display(description="Next Drawing Date")
    def get_next_drawing_date(self, obj):
        """Affiche la prochaine date de tirage"""
        return obj.next_drawing_date.strftime(
            "%Y-%m-%d %H:%M"
        )  # Formate la date comme vous le souhaitez

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

    @admin.action(description="Marquer les loteries sélectionnées comme annulées")
    def mark_cancelled(self, request, queryset):
        """
        Marquer les loteries comme 'cancelled' et retirer le gagnant.
        """
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
