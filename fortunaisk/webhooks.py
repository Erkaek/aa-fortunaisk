# fortunaisk/webhooks.py

from django.db import models


class WebhookConfiguration(models.Model):
    """
    Configuration pour le Webhook Discord.
    """

    webhook_url = models.URLField("URL du Webhook")

    class Meta:
        verbose_name = "Configuration du Webhook"

    def __str__(self):
        return self.webhook_url
