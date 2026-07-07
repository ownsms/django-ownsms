import json
from unittest import mock

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Message, Sim, Webhook, WebhookDelivery
from ownsms.services import dispatch, webhooks
from ownsms.tokens import new_api_key


@pytest.fixture
def ctx(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    sim = Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return acc, dev, sim, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


@pytest.mark.django_db
def test_configure_and_fire(ctx):
    acc, dev, sim, h = ctx
    r = Client().put(
        "/api/v1/webhook",
        data=json.dumps({"url": "https://example.test/hook", "events": ["message.sent"], "enabled": True}),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 200 and r.json()["secret"]
    m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="dispatched")
    dispatch.report_status(dev, m.id, "sent")
    assert WebhookDelivery.objects.filter(status="pending", event="message.sent").count() == 1


@pytest.mark.django_db
def test_not_subscribed_does_not_fire(ctx):
    acc, dev, sim, h = ctx
    Webhook.objects.create(account=acc, secret="s", url="https://x.test", events=["message.delivered"], enabled=True)
    m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="dispatched")
    dispatch.report_status(dev, m.id, "sent")
    assert WebhookDelivery.objects.count() == 0  # only message.delivered subscribed


@pytest.mark.django_db
def test_send_pending_delivers_on_2xx(ctx):
    acc, dev, sim, h = ctx
    Webhook.objects.create(account=acc, secret="s", url="https://x.test", events=["message.sent"], enabled=True)
    m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="dispatched")
    dispatch.report_status(dev, m.id, "sent")
    with mock.patch("ownsms.services.webhooks.urllib.request.urlopen") as u:
        u.return_value.__enter__ = lambda s: s
        u.return_value.__exit__ = lambda *a: False
        assert webhooks.send_pending() == 1
    assert WebhookDelivery.objects.get().status == "delivered"


@pytest.mark.django_db
def test_send_pending_retries_on_failure(ctx):
    acc, dev, sim, h = ctx
    Webhook.objects.create(account=acc, secret="s", url="https://x.test", events=["message.sent"], enabled=True)
    m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="dispatched")
    dispatch.report_status(dev, m.id, "sent")
    with mock.patch("ownsms.services.webhooks.urllib.request.urlopen", side_effect=Exception("boom")):
        webhooks.send_pending()
    d = WebhookDelivery.objects.get()
    assert d.status == "pending" and d.attempts == 1 and d.next_retry_at is not None
