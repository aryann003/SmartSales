import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order

N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/new-order"

@receiver(post_save, sender=Order)
def notify_n8n_on_order_created(sender, instance, created, **kwargs):
    if created: 
        payload = {
            "order_id": instance.id,
            "customer_id": instance.customer.id,
            "amount": float(instance.total_amount),
            "status": instance.status,
        }
        try:
            requests.post(N8N_WEBHOOK_URL, json=payload, timeout=5)
        except requests.exceptions.RequestException as e:
            print(f"Failed to notify n8n: {e}")