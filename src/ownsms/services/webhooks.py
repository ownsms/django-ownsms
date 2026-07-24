import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
import urllib.request
from datetime import timedelta
from urllib.parse import urlparse

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


def _check_url(url):
    """SSRF guard: raise ValueError unless url is a public http(s) destination.
    Rejects non-http(s) schemes and hosts resolving to private/loopback/link-local/
    reserved/multicast IPs. ponytail: getaddrinfo TOCTOU vs urlopen's re-resolve is
    accepted (DNS-rebinding); pin the IP if that threat becomes real."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"blocked scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("missing host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for info in socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise ValueError(f"blocked destination IP: {ip}")


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    """Re-run the SSRF check on redirect targets so a 3xx can't jump to an internal host."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Opener with only http(s) handlers — no FileHandler/FTPHandler, so file:// and ftp:// can't be reached.
_opener = urllib.request.OpenerDirector()
for _h in (
    urllib.request.ProxyHandler,
    urllib.request.HTTPHandler,
    urllib.request.HTTPSHandler,
    urllib.request.HTTPDefaultErrorHandler,
    _GuardedRedirect,
    urllib.request.HTTPErrorProcessor,
):
    _opener.add_handler(_h())


def send_pending(now=None):
    now = now or timezone.now()
    delivered = 0
    deadline = time.monotonic() + 50  # don't outlast the dispatch interval
    pending = list(WebhookDelivery.objects.filter(status="pending", next_retry_at__lte=now)[:100])
    # One query for all secrets instead of one per delivery (was N+1).
    secret_by_account = dict(
        Webhook.objects.filter(account_id__in={d.account_id for d in pending}).values_list("account_id", "secret")
    )
    for d in pending:
        if time.monotonic() > deadline:
            break
        secret = secret_by_account.get(d.account_id, "")
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
            _check_url(d.url)  # SSRF guard at the egress point (covers webhook url + callback_url)
            _opener.open(req, timeout=5)  # raises on non-2xx
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
