# fortunaisk/migrations/0004_consolidate_ticketpurchases.py
# Django
from django.db import migrations, models
from django.db.models import Count, Sum


def consolidate_ticketpurchases(apps, schema_editor):
    TP = apps.get_model("fortunaisk", "TicketPurchase")

    # 1) Regrouper par lottery/user/character
    groups = TP.objects.values("lottery_id", "user_id", "character_id").annotate(
        total_qty=Count("pk"),
        total_amt=Sum("amount"),
    )

    for g in groups:
        qs = TP.objects.filter(
            lottery_id=g["lottery_id"],
            user_id=g["user_id"],
            character_id=g["character_id"],
        ).order_by("id")
        first = qs.first()
        if not first:
            continue

        # 2) Mettre à jour la première ligne du groupe
        first.quantity = g["total_qty"]
        first.amount = g["total_amt"]
        first.save(update_fields=["quantity", "amount"])

        # 3) Supprimer les doublons (toutes les autres lignes)
        qs.exclude(pk=first.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        (
            "fortunaisk",
            "0003_ticketpurchase_quantity_alter_ticketpurchase_amount_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            consolidate_ticketpurchases, reverse_code=migrations.RunPython.noop
        ),
        # Si tu veux explicitement ajouter une contrainte unique après consolidation :
        migrations.AddConstraint(
            model_name="ticketpurchase",
            constraint=models.UniqueConstraint(
                fields=["lottery", "user", "character"],
                name="unique_ticketpurchase_per_user_character",
            ),
        ),
    ]
