from django.db.models.signals import post_save
from django.dispatch import receiver

from core.automation import dispatch_webhook, order_created_payload

from .models import Order


@receiver(post_save, sender=Order)
def notify_n8n_on_order_created(sender, instance, created, **kwargs):
    """Tell the automation layer about new orders (signed, async, retried)."""
    if created:
        dispatch_webhook("order.created", order_created_payload(instance))
