import json

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Sim


@pytest.fixture
def auth_header(db):
    from ownsms.tokens import new_api_key

    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return {"HTTP_AUTHORIZATION": f"Bearer {full}"}


@pytest.mark.django_db
def test_send_and_get(auth_header):
    c = Client()
    r = c.post(
        "/api/v1/messages",
        data=json.dumps({"to": "901110000", "text": "hi"}),
        content_type="application/json",
        **auth_header,
    )
    assert r.status_code == 202, r.content
    mid = r.json()["id"]
    g = c.get(f"/api/v1/messages/{mid}", **auth_header)
    assert g.status_code == 200 and g.json()["status"] == "queued"


@pytest.mark.django_db
def test_unauthorized():
    c = Client()
    r = c.post("/api/v1/messages", data="{}", content_type="application/json")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


@pytest.mark.django_db
def test_message_detail_non_numeric_id_returns_404(auth_header):
    c = Client()
    r = c.get("/api/v1/messages/abc", **auth_header)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
