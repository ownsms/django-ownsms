import json

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Message, Sim, WebhookDelivery
from ownsms.tokens import new_api_key


@pytest.fixture
def ctx(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    sim = Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return acc, dev, sim, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


def _mk(acc, dev, sim, n, **kw):
    return [
        Message.objects.create(account=acc, device=dev, sim=sim, to="+99890000000" + str(i), text="x", **kw)
        for i in range(n)
    ]


@pytest.mark.django_db
def test_messages_pagination_and_filter(ctx):
    acc, dev, sim, h = ctx
    _mk(acc, dev, sim, 3, status="sent")
    _mk(acc, dev, sim, 2, status="failed")
    c = Client()
    page = c.get("/api/v1/messages?limit=2", **h).json()
    assert len(page["data"]) == 2 and page["next_before"]
    page2 = c.get(f"/api/v1/messages?limit=2&before={page['next_before']}", **h).json()
    assert len(page2["data"]) >= 1
    only_failed = c.get("/api/v1/messages?status=failed", **h).json()
    assert all(m["status"] == "failed" for m in only_failed["data"]) and len(only_failed["data"]) == 2


@pytest.mark.django_db
def test_campaign_messages_list(ctx):
    acc, dev, sim, h = ctx
    cid = (
        Client()
        .post(
            "/api/v1/campaigns",
            data=json.dumps({"text": "hi", "recipients": [{"to": "901110001"}, {"to": "901110002"}]}),
            content_type="application/json",
            **h,
        )
        .json()["id"]
    )
    r = Client().get(f"/api/v1/campaigns/{cid}/messages", **h)
    assert r.status_code == 200 and len(r.json()["data"]) == 2


@pytest.mark.django_db
def test_webhook_deliveries_list(ctx):
    acc, dev, sim, h = ctx
    WebhookDelivery.objects.create(
        account=acc, event_id="e1", event="message.sent", url="https://x.test", payload={}, status="delivered"
    )
    r = Client().get("/api/v1/webhook/deliveries", **h)
    assert r.status_code == 200 and r.json()["data"][0]["event"] == "message.sent"
