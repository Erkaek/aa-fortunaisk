"""App Configuration"""

# Django
from django.apps import AppConfig

# AA fortunaisk App
from fortunaisk import __version__


class fortunaiskConfig(AppConfig):
    """App Config"""

    name = "fortunaISK"
    label = "fortunaISK"
    verbose_name = f"fortunaISK App v{__version__}"
