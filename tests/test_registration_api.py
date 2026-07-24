import json

import pytest
from django.test import Client

from ownsms.models import Account, Device, Sim


@pytest.mark.django_db
def test_register_creates_account_device_key():
    r = Client().post(
        "/api/v1/register",
        data=json.dumps(
            {
                "email": "a@b.uz",
                "device_name": "A52",
                "sims": [{"subscription_id": 1, "number": "+998901112233", "is_default": True}],
            }
        ),
        content_type="application/json",
    )
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["device_token"]
    assert body["api_key"].startswith("osk_")
    assert Account.objects.count() == 1
    assert Device.objects.count() == 1
    assert Sim.objects.filter(subscription_id=1).exists()


@pytest.mark.django_db
def test_pairing_flow():
    c = Client()
    dev_token = c.post("/api/v1/register", data=json.dumps({}), content_type="application/json").json()["device_token"]
    h = {"HTTP_AUTHORIZATION": f"Bearer {dev_token}"}
    code = c.post("/api/v1/devices/pairing-code", **h).json()["code"]
    r2 = c.post("/api/v1/register/pair", data=json.dumps({"code": code}), content_type="application/json")
    assert r2.status_code == 201 and r2.json()["device_token"]
    assert Device.objects.count() == 2
    # reuse rejected
    r3 = c.post("/api/v1/register/pair", data=json.dumps({"code": code}), content_type="application/json")
    assert r3.status_code == 400


@pytest.mark.django_db
def test_pairing_code_is_32_hex_chars():
    c = Client()
    dev_token = c.post("/api/v1/register", data=json.dumps({}), content_type="application/json").json()["device_token"]
    code = c.post(
        "/api/v1/devices/pairing-code", **{"HTTP_AUTHORIZATION": f"Bearer {dev_token}"}
    ).json()["code"]
    assert len(code) == 32 and all(ch in "0123456789abcdef" for ch in code)
