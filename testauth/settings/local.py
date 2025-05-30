"""
Test settings
"""

# flake8: noqa

from .base import *

PACKAGE = "fortunaisk"

# Test database - utiliser SQLite en mémoire pour les tests
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {
            "NAME": ":memory:",
        },
    }
}

# Marquer comme environnement de test
TESTING = True

# Static files
STATICFILES_DIRS = [
    f"{PACKAGE}/static",
]

SITE_URL = "https://example.com"
CSRF_TRUSTED_ORIGINS = [SITE_URL]
DISCORD_BOT_TOKEN = "My_Dummy_Token"

# Django configuration
ROOT_URLCONF = "testauth.urls"
WSGI_APPLICATION = "testauth.wsgi.application"
SECRET_KEY = "t$@h+j#yqhmuy$x7$fkhytd&drajgfsb-6+j9pqn*vj0)gq&-2"
STATIC_ROOT = "/var/www/testauth/static/"
SITE_NAME = "testauth"
DEBUG = True  # Activé pour les tests pour voir les erreurs

# Notifications
NOTIFICATIONS_REFRESH_TIME = 30
NOTIFICATIONS_MAX_PER_USER = 50

# S'assurer que django-celery-beat est installé pour les tests
INSTALLED_APPS += [
    "django_celery_beat",  # IMPORTANT: Ajouté pour les tests
    PACKAGE,
]

# Celery settings pour les tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Cache simple pour les tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Logging pour les tests - plus verbeux pour débugger
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "fortunaisk": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# ESI Settings (dummy pour les tests)
ESI_SSO_CLIENT_ID = "dummy"
ESI_SSO_CLIENT_SECRET = "dummy"
ESI_SSO_CALLBACK_URL = "http://localhost:8000"

# Email settings (désactivé pour les tests)
REGISTRATION_VERIFY_EMAIL = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Apps avec vues publiques
APPS_WITH_PUBLIC_VIEWS = []
