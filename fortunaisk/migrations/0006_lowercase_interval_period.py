# fortunaisk/migrations/0006_lowercase_interval_period.py
from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("fortunaisk", "0005_remove_ticketpurchase_unique_ticketpurchase_per_user_character"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                -- passe toutes les périodes en minuscules pour éviter le TypeError
                UPDATE django_celery_beat_intervalschedule
                   SET period = LOWER(period)
                 WHERE period <> LOWER(period);
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
