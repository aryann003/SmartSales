from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=get_user_model())
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Every user gets a Profile so role checks never hit a missing relation.

    New accounts default to the least-privileged business role (salesperson);
    a superuser is created as admin.
    """
    if created:
        Profile.objects.get_or_create(
            user=instance, defaults={"role": "admin" if instance.is_superuser else "salesperson"}
        )
