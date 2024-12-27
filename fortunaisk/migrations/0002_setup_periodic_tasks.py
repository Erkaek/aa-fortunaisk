# fortunaisk/migrations/000X_setup_periodic_tasks.py

from django.db import migrations


def setup_periodic_tasks_func(apps, schema_editor):
    """
    Exécute la fonction de configuration des tâches périodiques.
    """
    from fortunaisk.tasks import setup_periodic_tasks
    setup_periodic_tasks()


class Migration(migrations.Migration):

    dependencies = [
        ('fortunaisk', '0001_initial.py'),  # Remplacez par le nom de votre dernière migration
    ]

    operations = [
        migrations.RunPython(setup_periodic_tasks_func),
    ]
