import json

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Sim
from ownsms.tokens import new_api_key


def _acct_with_key(scopes):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=scopes)
    return acc, dev, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


@pytest.fixture
def readonly(db):
    return _acct_with_key(["read"])


@pytest.fixture
def sender(db):
    return _acct_with_key(["send", "read"])


@pytest.mark.django_db
def test_readonly_cannot_create_key(readonly):
    _, _, h = readonly
    r = Client().post("/api/v1/keys", data=json.dumps({}), content_type="application/json", **h)
    assert r.status_code == 403


@pytest.mark.django_db
def test_send_key_can_create_key(sender):
    _, _, h = sender
    r = Client().post("/api/v1/keys", data=json.dumps({"scopes": ["read"]}), content_type="application/json", **h)
    assert r.status_code == 201 and r.json()["scopes"] == ["read"]


@pytest.mark.django_db
def test_cannot_grant_scope_beyond_own(sender):
    # A read+send key still cannot mint a scope it does not hold.
    _, _, h = sender
    r = Client().post(
        "/api/v1/keys", data=json.dumps({"scopes": ["send", "read", "admin"]}), content_type="application/json", **h
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_readonly_cannot_revoke_key(readonly):
    acc, _, h = readonly
    victim = ApiKey.objects.filter(account=acc).first()
    r = Client().post(f"/api/v1/keys/{victim.id}/revoke", **h)
    assert r.status_code == 403
    victim.refresh_from_db()
    assert victim.revoked is False


@pytest.mark.django_db
def test_readonly_cannot_repoint_webhook(readonly):
    _, _, h = readonly
    r = Client().put(
        "/api/v1/webhook",
        data=json.dumps({"url": "https://evil.test/hook", "enabled": True}),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 403


@pytest.mark.django_db
def test_send_key_can_repoint_webhook(sender):
    _, _, h = sender
    r = Client().put(
        "/api/v1/webhook",
        data=json.dumps({"url": "https://example.test/hook", "events": ["message.sent"], "enabled": True}),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 200 and r.json()["url"] == "https://example.test/hook"


@pytest.mark.django_db
def test_readonly_cannot_toggle_device(readonly):
    acc, dev, h = readonly
    r = Client().post(f"/api/v1/devices/{dev.id}/deactivate", **h)
    assert r.status_code == 403
    dev.refresh_from_db()
    assert dev.status == "active"


@pytest.mark.django_db
def test_send_key_can_toggle_device(sender):
    acc, dev, h = sender
    r = Client().post(f"/api/v1/devices/{dev.id}/deactivate", **h)
    assert r.status_code == 200 and r.json()["status"] == "inactive"
