# app_settings.py
from django.conf import settings

PAYMENT_CORP = getattr(settings, "PAYMENT_CORP", 123456789)
