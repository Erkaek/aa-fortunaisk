# fortunaisk/signals/user_signals.py

# Django
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
