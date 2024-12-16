# apps.py
from django.apps import AppConfig
from fortunaisk import __version__

class FortunaISKConfig(AppConfig):
    name = "fortunaisk"
    label = "fortunaisk"
    verbose_name = f"FortunaISK App v{__version__}"
