# fortunaisk/apps.py
# Standard Library
import logging

# Django
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class FortunaIskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fortunaisk"

    def ready(self) -> None:
        pass
