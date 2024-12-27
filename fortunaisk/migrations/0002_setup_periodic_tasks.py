# fortunaisk/migrations/0002_setup_periodic_tasks.py

# Django
from django.db import migrations


def setup_periodic_tasks_func(apps, schema_editor):
    """
    Exécute la fonction de configuration des tâches périodiques.
    """
    # fortunaisk
    from fortunaisk.tasks import setup_periodic_tasks

    setup_periodic_tasks()


class Migration(migrations.Migration):

    dependencies = [
        ("fortunaisk", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(setup_periodic_tasks_func),
    ]
