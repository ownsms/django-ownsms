import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Message, Sim
from ownsms.tokens import new_api_key


@pytest.fixture
def ctx(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    sim = Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return acc, dev, sim, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


def _msg(acc, dev, sim, **kw):
    return Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi there", **kw)


@pytest.mark.django_db
def test_dispatched_is_serialized_as_sending(ctx):
    acc, dev, sim, h = ctx
    m = _msg(acc, dev, sim, status="dispatched")
    # DB keeps the internal name; the public API presents "sending".
    assert Message.objects.get(pk=m.pk).status == "dispatched"
    listed = Client().get("/api/v1/messages", **h).json()["data"][0]
    assert listed["status"] == "sending"
    detail = Client().get(f"/api/v1/messages/msg_{m.id}", **h).json()
    assert detail["status"] == "sending"


@pytest.mark.django_db
def test_filter_by_sending_matches_dispatched(ctx):
    acc, dev, sim, h = ctx
    _msg(acc, dev, sim, status="dispatched")
    _msg(acc, dev, sim, status="sent")
    only = Client().get("/api/v1/messages?status=sending", **h).json()["data"]
    assert len(only) == 1 and only[0]["status"] == "sending"


@pytest.mark.django_db
def test_message_serialization_includes_text(ctx):
    acc, dev, sim, h = ctx
    _msg(acc, dev, sim, status="sent")
    listed = Client().get("/api/v1/messages", **h).json()["data"][0]
    assert listed["text"] == "hi there"


@pytest.mark.django_db
def test_device_status_reports_today_sent(ctx):
    acc, dev, sim, h = ctx
    _msg(acc, dev, sim, status="sent", sent_at=timezone.now())
    _msg(acc, dev, sim, status="queued")  # not sent → not counted
    status = Client().get("/api/v1/device", **h).json()
    assert status["today_sent"] == 1
