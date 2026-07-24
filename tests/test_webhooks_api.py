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
    with mock.patch("ownsms.services.webhooks._check_url"), mock.patch("ownsms.services.webhooks._opener.open"):
        assert webhooks.send_pending() == 1
    assert WebhookDelivery.objects.get().status == "delivered"


@pytest.mark.django_db
def test_send_pending_retries_on_failure(ctx):
    acc, dev, sim, h = ctx
    Webhook.objects.create(account=acc, secret="s", url="https://x.test", events=["message.sent"], enabled=True)
    m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="dispatched")
    dispatch.report_status(dev, m.id, "sent")
    with (
        mock.patch("ownsms.services.webhooks._check_url"),
        mock.patch("ownsms.services.webhooks._opener.open", side_effect=Exception("boom")),
    ):
        webhooks.send_pending()
    d = WebhookDelivery.objects.get()
    assert d.status == "pending" and d.attempts == 1 and d.next_retry_at is not None


@pytest.mark.django_db
def test_send_pending_blocks_ssrf_targets(ctx):
    """file:// scheme and a private-IP host are rejected before any network call."""
    acc, dev, sim, h = ctx
    Webhook.objects.create(account=acc, secret="s", url="https://x.test", events=["message.sent"], enabled=True)
    for bad_url in ("file:///etc/passwd", "http://127.0.0.1:8080/hook", "http://169.254.169.254/latest"):
        m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="dispatched")
        d = WebhookDelivery.objects.create(
            account=acc,
            event_id=f"e{m.id}",
            event="message.sent",
            message=m,
            url=bad_url,
            payload={"x": 1},
            next_retry_at=timezone.now(),
            status="pending",
        )
        # _opener.open must never be reached for a blocked target.
        with mock.patch("ownsms.services.webhooks._opener.open", side_effect=AssertionError("egress attempted")):
            assert webhooks.send_pending() == 0
        d.refresh_from_db()
        assert d.status == "pending" and d.attempts == 1  # failed the guard, will retry


def test_check_url_rejects_scheme_and_private_ip():
    with pytest.raises(ValueError):
        webhooks._check_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        webhooks._check_url("ftp://example.test/x")
    with pytest.raises(ValueError):
        webhooks._check_url("http://127.0.0.1/hook")  # loopback
