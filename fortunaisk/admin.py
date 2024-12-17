# Django
from django.contrib import admin

from .models import Lottery, TicketPurchase, Winner


@admin.register(Lottery)
class LotteryAdmin(admin.ModelAdmin):
    list_display = (
        "lottery_reference",
        "is_active",
        "winner_name",
        "next_drawing_date",
    )
    search_fields = ("lottery_reference", "winner_name")
    actions = ["mark_completed", "mark_cancelled"]
    readonly_fields = ("lottery_reference", "winner_name")  # Champs en lecture seule

    def save_model(self, request, obj, form, change):
        """
        Automatiquement générer 'lottery_reference' lors de la sauvegarde.
        """
        if not obj.lottery_reference:
            start_date_str = (
                obj.start_date.strftime("%Y%m%d") if obj.start_date else "00000000"
            )
            end_date_str = (
                obj.end_date.strftime("%Y%m%d") if obj.end_date else "99999999"
            )
            obj.lottery_reference = f"LOTTERY-{start_date_str}-{end_date_str}"
        super().save_model(request, obj, form, change)

    @admin.action(description="Marquer les loteries sélectionnées comme complétées")
    def mark_completed(self, request, queryset):
        """
        Marquer les loteries comme 'completed' et définir le gagnant.
        """
        for lottery in queryset.filter(status="active"):
            # Générer un gagnant si aucun n'est défini
            if not lottery.winner_name:
                ticket = (
                    TicketPurchase.objects.filter(lottery=lottery).order_by("?").first()
                )
                if ticket:
                    lottery.winner_name = ticket.character.character_name
                else:
                    self.message_user(
                        request,
                        f"Aucun ticket disponible pour la loterie {lottery.lottery_reference}.",
                    )
                    continue

            lottery.status = "completed"
            lottery.save()
            self.message_user(
                request, f"Loterie {lottery.lottery_reference} marquée comme complétée."
            )

    @admin.action(description="Marquer les loteries sélectionnées comme annulées")
    def mark_cancelled(self, request, queryset):
        """
        Marquer les loteries comme 'cancelled' et retirer le gagnant.
        """
        queryset.update(status="cancelled", winner_name=None)
        self.message_user(request, "Loteries marquées comme annulées.")


@admin.register(TicketPurchase)
class TicketPurchaseAdmin(admin.ModelAdmin):
    list_display = ("user", "character", "lottery", "amount", "date")
    search_fields = ("user__username", "character__character_name")


@admin.register(Winner)
class WinnerAdmin(admin.ModelAdmin):
    list_display = ("character", "ticket", "won_at")
    readonly_fields = (
        "ticket",
        "character",
        "won_at",
    )  # Empêche l'édition manuelle des données
