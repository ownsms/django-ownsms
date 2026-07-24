from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .. import conf
from ..errors import ApiError
from ..models import Message
from . import webhooks


def claim_jobs(device, now):
    lease = now + timedelta(seconds=conf.get("LEASE_SECONDS"))
    batch = conf.get("POLL_BATCH_SIZE")
    with transaction.atomic():
        ids = list(
            Message.objects.select_for_update()
            .filter(device=device, status="queued")
            .filter(Q(scheduled_at__isnull=True) | Q(scheduled_at__lte=now))
            .exclude(campaign__status__in=["paused", "canceled"])
            .order_by("id")
            .values_list("id", flat=True)[:batch]
        )
        Message.objects.filter(id__in=ids).update(status="dispatched", dispatched_at=now, lease_expires_at=lease)
    return list(Message.objects.filter(id__in=ids).select_related("sim").order_by("id"))


def report_status(device, message_id, status, error_code=""):
    m = Message.objects.filter(device=device, pk=message_id).first()
    if not m:
        raise ApiError("not_found", "Job not found", 404)
    allowed = {"sent": {"dispatched"}, "delivered": {"sent"}, "failed": {"dispatched", "sent"}}
    if status not in allowed:
        raise ApiError("bad_status", f"Unknown status {status}", 400)
    # A lease_timeout is a *guess* that the device died mid-send. If the device later reports the
    # real outcome (it was actually sent — common on OEM phones that kill the app), believe it and
    # recover the job. A genuine failure (any other error_code) stays failed.
    recovering = m.status == "failed" and m.error_code == "lease_timeout"
    if m.status not in allowed[status] and not recovering:
        return m  # stale/invalid transition ignored
    now = timezone.now()
    if status == "sent":
        m.status, m.sent_at, m.error_code = "sent", now, ""  # clear a recovered lease_timeout
    elif status == "delivered":
        m.status, m.delivered_at, m.error_code = "delivered", now, ""
        if m.sent_at is None:  # lease_timeout->delivered recovery skipped 'sent'; keep today_sent count honest
            m.sent_at = now
    else:
        m.status, m.error_code = "failed", error_code or "send_failed"
    m.save(update_fields=["status", "sent_at", "delivered_at", "error_code"])
    webhooks.enqueue(m, m.status)
    return m


def expire_and_reclaim(now):
    expired = 0
    queued = Message.objects.filter(status="queued", ttl__isnull=False).only(
        "id", "created_at", "ttl", "account_id", "to"
    )
    for m in queued.iterator():
        if m.created_at + timedelta(seconds=m.ttl) > now:
            continue
        rows = Message.objects.filter(pk=m.pk, status="queued").update(status="expired")
        if rows:
            webhooks.enqueue(m, "expired")
        expired += rows
    reclaimed = Message.objects.filter(status="dispatched", lease_expires_at__lte=now).update(
        status="failed", error_code="lease_timeout"
    )
    return {"expired": expired, "reclaimed": reclaimed}
