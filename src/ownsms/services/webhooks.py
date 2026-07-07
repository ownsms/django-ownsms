import hashlib
import hmac
import json
import secrets
import urllib.request
from datetime import timedelta

from django.utils import timezone

from ..models import Webhook, WebhookDelivery

EVENTS = {
    "sent": "message.sent",
    "delivered": "message.delivered",
    "failed": "message.failed",
    "expired": "message.expired",
}
MAX_ATTEMPTS = 5


def get_or_create_config(account):
    wh, _ = Webhook.objects.get_or_create(account=account, defaults={"secret": secrets.token_hex(16)})
    return wh


def enqueue(message, status):
    """Create a pending delivery if the account has an enabled webhook subscribed to this event.
    Never raises — webhook problems must not break the caller."""
    try:
        event = EVENTS.get(status)
        if not event:
            return
        wh = Webhook.objects.filter(account_id=message.account_id, enabled=True).first()
        if not wh or event not in wh.events:
            return
        url = getattr(message, "callback_url", None) or wh.url
        if not url:
            return
        now = timezone.now()
        payload = {
            "event_id": secrets.token_hex(12),
            "event": event,
            "message_id": f"msg_{message.id}",
            "status": status,
            "to": message.to,
            "from": message.sim.number if message.sim else None,
            "timestamp": now.isoformat(),
        }
        WebhookDelivery.objects.create(
            account_id=message.account_id,
            event_id=payload["event_id"],
            event=event,
            message=message,
            url=url,
            payload=payload,
            next_retry_at=now,
        )
    except Exception:
        pass


def _sign(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def send_pending(now=None):
    now = now or timezone.now()
    delivered = 0
    for d in list(WebhookDelivery.objects.filter(status="pending", next_retry_at__lte=now)[:100]):
        wh = Webhook.objects.filter(account_id=d.account_id).first()
        secret = wh.secret if wh else ""
        body = json.dumps(d.payload).encode()
        req = urllib.request.Request(
            d.url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Ownsms-Event": d.event,
                "X-Ownsms-Signature": _sign(secret, body),
            },
        )
        try:
            urllib.request.urlopen(req, timeout=10)  # raises on non-2xx
            ok = True
        except Exception:
            ok = False
        d.attempts += 1
        if ok:
            d.status = "delivered"
            delivered += 1
        elif d.attempts >= MAX_ATTEMPTS:
            d.status = "failed"
        else:
            d.next_retry_at = now + timedelta(minutes=2**d.attempts)
        d.save(update_fields=["attempts", "status", "next_retry_at"])
    return delivered
