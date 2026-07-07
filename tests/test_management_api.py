import json

import pytest
from django.test import Client, RequestFactory
from django.utils import timezone

from ownsms.auth import resolve_device
from ownsms.errors import ApiError
from ownsms.models import Account, ApiKey, Device, Sim
from ownsms.tokens import new_api_key


@pytest.fixture
def ctx(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return acc, dev, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


@pytest.mark.django_db
def test_create_list_revoke_key(ctx):
    acc, dev, h = ctx
    c = Client()
    r = c.post(
        "/api/v1/keys",
        data=json.dumps({"name": "server", "device_id": dev.id}),
        content_type="application/json",
        **h,
    )
    assert r.status_code == 201
    new_full = r.json()["api_key"]
    assert new_full.startswith("osk_")
    kid = r.json()["id"]
    lst = c.get("/api/v1/keys", **h)
    assert lst.status_code == 200 and any(k["id"] == kid for k in lst.json()["data"])
    assert "key_hash" not in lst.json()["data"][0]
    # revoke -> the new key no longer authenticates
    c.post(f"/api/v1/keys/{kid}/revoke", **h)
    assert ApiKey.objects.get(pk=kid).revoked


@pytest.mark.django_db
def test_devices_list_and_deactivate(ctx):
    acc, dev, h = ctx
    c = Client()
    lst = c.get("/api/v1/devices", **h)
    assert lst.status_code == 200 and lst.json()["data"][0]["id"] == dev.id
    c.post(f"/api/v1/devices/{dev.id}/deactivate", **h)
    dev.refresh_from_db()
    assert dev.status == "inactive"
    # inactive device can't authenticate for the device protocol
    from ownsms.tokens import hash_token

    dev.device_token = hash_token("dt")
    dev.save()
    req = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer dt")
    with pytest.raises(ApiError):
        resolve_device(req)
