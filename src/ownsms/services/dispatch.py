from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .. import conf
from ..errors import ApiError
from ..models import Message
from . import webhooks


def claim_jobs(device, now):
    lease = now + timedelta(seconds=conf.get("LEASE_SECONDS"))
    batch = conf.get("POLL_BATCH_SIZE")
    with transaction.atomic():
        from django.db.models import Q

        ids = list(
            Message.objects.select_for_update()
            .filter(device=device, status="queued")
            .filter(Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now))
            .exclude(campaign__status__in=["paused", "canceled"])
            .order_by("id")
            .values_list("id", flat=True)[:batch]
        )
        Message.objects.filter(id__in=ids).update(status="dispatched", dispatched_at=now, lease_expires_at=lease)
    return list(Message.objects.filter(id__in=ids).order_by("id"))


def report_status(device, message_id, status, error_code=""):
    m = Message.objects.filter(device=device, pk=message_id).first()
    if not m:
        raise ApiError("not_found", "Job not found", 404)
    allowed = {"sent": {"dispatched"}, "delivered": {"sent"}, "failed": {"dispatched", "sent"}}
    if status not in allowed:
        raise ApiError("bad_status", f"Unknown status {status}", 400)
    if m.status not in allowed[status]:
        return m  # stale/invalid transition ignored
    now = timezone.now()
    if status == "sent":
        m.status, m.sent_at = "sent", now
    elif status == "delivered":
        m.status, m.delivered_at = "delivered", now
    else:
        m.status, m.error_code = "failed", error_code or "send_failed"
    m.save(update_fields=["status", "sent_at", "delivered_at", "error_code"])
    webhooks.enqueue(m, m.status)
    return m


def expire_and_reclaim(now):
    expired = 0
    for m in Message.objects.filter(status="queued", ttl__isnull=False):
        if m.created_at + timedelta(seconds=m.ttl) <= now:
            rows = Message.objects.filter(pk=m.pk, status="queued").update(status="expired")
            if rows:
                webhooks.enqueue(m, "expired")
            expired += rows
    reclaimed = Message.objects.filter(status="dispatched", lease_expires_at__lte=now).update(
        status="failed", error_code="lease_timeout"
    )
    return {"expired": expired, "reclaimed": reclaimed}
