"""App Configuration"""

# Django
from django.apps import AppConfig

# AA fortunaisk App
from fortunaisk import __version__


class fortunaiskConfig(AppConfig):
    """App Config"""

    name = "fortunaisk"
    label = "fortunaisk"
    verbose_name = f"fortunaisk App v{__version__}"
