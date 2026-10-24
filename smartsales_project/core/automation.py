"""Outbound automation: signed webhooks with retries and an audit trail.

Design goals
------------
* **Authentic**: every request is signed with HMAC-SHA256 over ``timestamp.body``
  so the receiver (e.g. n8n) can verify who sent it and reject replays.
* **Non-blocking**: delivery is scheduled with ``transaction.on_commit`` and runs
  in a background thread, so slow receivers never slow down order creation and
  webhooks are never sent for rolled-back orders.
* **Resilient**: network errors, 429 and 5xx responses are retried with
  exponential backoff; other 4xx responses are not.
* **Observable**: every attempt is recorded in ``AutomationLog``.
"""
import hashlib
import hmac
import json
import logging
import threading
import time

import requests
from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from .models import AutomationLog

logger = logging.getLogger("smartsales.automation")

SIGNATURE_HEADER = "X-SmartSales-Signature"
TIMESTAMP_HEADER = "X-SmartSales-Timestamp"
EVENT_HEADER = "X-SmartSales-Event"
SIGNATURE_TOLERANCE_SECONDS = 300


def sign_payload(secret: str, timestamp: str, body: bytes) -> str:
    """Return ``sha256=<hex>`` for ``timestamp + "." + body``."""
    message = timestamp.encode() + b"." + body
    return "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(secret, timestamp, body, signature, *, now=None) -> bool:
    """Check a signature and reject stale timestamps (replay protection)."""
    try:
        age = abs((now if now is not None else time.time()) - int(timestamp))
    except (TypeError, ValueError):
        return False
    if age > SIGNATURE_TOLERANCE_SECONDS or not secret or not signature:
        return False
    expected = sign_payload(secret, str(timestamp), body)
    return hmac.compare_digest(expected, signature)


def record(workflow_name, event_type, status, message=""):
    return AutomationLog.objects.create(
        workflow_name=workflow_name,
        event_type=event_type,
        status=status,
        message=str(message)[:2000],
    )


def _retryable(response) -> bool:
    return response.status_code == 429 or response.status_code >= 500


def deliver_webhook(event_type, payload, *, url=None, secret=None, sleep=time.sleep) -> bool:
    """Send one signed event, retrying transient failures. Returns True on success."""
    url = settings.N8N_WEBHOOK_URL if url is None else url
    secret = settings.WEBHOOK_SECRET if secret is None else secret
    workflow = f"{event_type} webhook"
    if not url:
        logger.info("Webhook for %s skipped: N8N_WEBHOOK_URL is not set", event_type)
        return False

    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    max_attempts = max(1, settings.WEBHOOK_MAX_ATTEMPTS)

    for attempt in range(1, max_attempts + 1):
        timestamp = str(int(time.time()))
        headers = {"Content-Type": "application/json", EVENT_HEADER: event_type, TIMESTAMP_HEADER: timestamp}
        if secret:
            headers[SIGNATURE_HEADER] = sign_payload(secret, timestamp, body)

        error, retry = None, True
        try:
            response = requests.post(url, data=body, headers=headers, timeout=settings.WEBHOOK_TIMEOUT_SECONDS)
            if response.ok:
                record(workflow, event_type, "SUCCESS", f"HTTP {response.status_code} on attempt {attempt}")
                return True
            error, retry = f"HTTP {response.status_code}", _retryable(response)
        except requests.exceptions.RequestException as exc:
            error = f"{type(exc).__name__}: {exc}"

        if retry and attempt < max_attempts:
            record(workflow, event_type, "RETRY", f"Attempt {attempt}/{max_attempts} failed: {error}")
            sleep(settings.WEBHOOK_BACKOFF_SECONDS * 2 ** (attempt - 1))
            continue

        record(workflow, event_type, "FAILED", f"Gave up after attempt {attempt}: {error}")
        logger.warning("Webhook %s failed: %s", event_type, error)
        return False
    return False  # pragma: no cover


def _run_in_thread(event_type, payload):
    try:
        deliver_webhook(event_type, payload)
    finally:
        close_old_connections()


def dispatch_webhook(event_type, payload, *, run_async=None):
    """Queue a webhook for delivery once the surrounding transaction commits.

    Set ``WEBHOOK_ASYNC=False`` (tests, scripts) to deliver inline at commit time.
    """
    if not settings.N8N_WEBHOOK_URL:
        return
    run_async = getattr(settings, "WEBHOOK_ASYNC", True) if run_async is None else run_async

    def _send():
        if run_async:
            threading.Thread(target=_run_in_thread, args=(event_type, payload), daemon=True).start()
        else:
            deliver_webhook(event_type, payload)

    transaction.on_commit(_send)


def order_created_payload(order):
    return {
        "event": "order.created",
        "occurred_at": timezone.now().isoformat(),
        "order_id": order.id,
        "customer_id": order.customer_id,
        "amount": float(order.total_amount),
        "status": order.status,
    }
