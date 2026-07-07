from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Sim, Webhook, WebhookDelivery
from ownsms.services import dispatch
from ownsms.services.messaging import create_message
from ownsms.tokens import new_api_key


def _ctx(is_test=False):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    key = ApiKey.objects.create(
        account=acc, device=dev, key_hash="h" + str(is_test), prefix="osk_a", scopes=["send", "read"], is_test=is_test
    )
    return acc, dev, key


@pytest.mark.django_db
def test_callback_url_stored_and_used_by_webhook():
    acc, dev, key = _ctx()
    Webhook.objects.create(account=acc, secret="s", url="https://default.test", events=["message.sent"], enabled=True)
    msg, _ = create_message(key, to="901110000", text="hi", callback_url="https://override.test")
    assert msg.callback_url == "https://override.test"
    msg.status = "dispatched"
    msg.save()
    dispatch.report_status(dev, msg.id, "sent")
    assert WebhookDelivery.objects.get().url == "https://override.test"  # per-message override


@pytest.mark.django_db
def test_send_at_defers_claim():
    acc, dev, key = _ctx()
    future = timezone.now() + timedelta(hours=1)
    msg, _ = create_message(key, to="901110000", text="hi", queued=True, send_at=future)
    assert msg.scheduled_at is not None
    assert dispatch.claim_jobs(dev, timezone.now()) == []  # not due yet
    assert len(dispatch.claim_jobs(dev, future + timedelta(seconds=1))) == 1


@pytest.mark.django_db
def test_cancel_queued_message():
    acc, dev, key = _ctx()
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    h = {"HTTP_AUTHORIZATION": f"Bearer {full}"}
    msg, _ = create_message(key, to="901110000", text="hi", queued=True)
    r = Client().post(f"/api/v1/messages/msg_{msg.id}/cancel", **h)
    assert r.status_code == 200 and r.json()["status"] == "canceled"
    assert dispatch.claim_jobs(dev, timezone.now()) == []


@pytest.mark.django_db
def test_test_key_simulates_delivery():
    acc, dev, key = _ctx(is_test=True)
    msg, _ = create_message(key, to="901110000", text="hi")
    assert msg.is_test and msg.status == "delivered"
    assert dispatch.claim_jobs(dev, timezone.now()) == []  # never dispatched to a device
