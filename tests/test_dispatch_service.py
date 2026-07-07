from datetime import timedelta

import pytest
from django.utils import timezone

from ownsms.models import Account, Device, Message, Sim
from ownsms.services.dispatch import claim_jobs, expire_and_reclaim, report_status


@pytest.fixture
def dev(db):
    acc = Account.objects.create(email="a@b.uz")
    d = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=d, subscription_id=1, number="+998901112233", is_default=True)
    return d


def _msg(dev, **kw):
    return Message.objects.create(
        account=dev.account, device=dev, sim=dev.sims.first(), to="+998900000000", text="hi", **kw
    )


@pytest.mark.django_db
def test_claim_marks_dispatched(dev):
    m = _msg(dev, status="queued")
    jobs = claim_jobs(dev, timezone.now())
    assert [j.id for j in jobs] == [m.id]
    m.refresh_from_db()
    assert m.status == "dispatched" and m.lease_expires_at is not None


@pytest.mark.django_db
def test_report_sent_then_delivered(dev):
    m = _msg(dev, status="dispatched")
    report_status(dev, m.id, "sent")
    m.refresh_from_db()
    assert m.status == "sent" and m.sent_at
    report_status(dev, m.id, "delivered")
    m.refresh_from_db()
    assert m.status == "delivered" and m.delivered_at


@pytest.mark.django_db
def test_report_failed_job_ignores_sent(dev):
    """A failed job must not flip back to sent."""
    m = _msg(dev, status="failed", error_code="send_failed")
    report_status(dev, m.id, "sent")
    m.refresh_from_db()
    assert m.status == "failed"


@pytest.mark.django_db
def test_report_queued_job_ignores_sent(dev):
    """A queued job (not yet dispatched) must not flip to sent."""
    m = _msg(dev, status="queued")
    report_status(dev, m.id, "sent")
    m.refresh_from_db()
    assert m.status == "queued"


@pytest.mark.django_db
def test_expire_and_reclaim(dev):
    old = timezone.now() - timedelta(seconds=10)
    q = _msg(dev, status="queued", ttl=1)
    Message.objects.filter(pk=q.pk).update(created_at=old)
    d = _msg(dev, status="dispatched", lease_expires_at=old)
    res = expire_and_reclaim(timezone.now())
    q.refresh_from_db()
    d.refresh_from_db()
    assert q.status == "expired" and d.status == "failed"
    assert res["expired"] == 1 and res["reclaimed"] == 1
