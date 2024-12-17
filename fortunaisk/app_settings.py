# fortunaisk/app_settings.py

# Django
from django.conf import settings

PAYMENT_CORP = getattr(settings, "PAYMENT_CORP", 123456789)
