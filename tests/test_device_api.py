import json

import pytest
from django.test import Client, override_settings
from django.utils import timezone

from ownsms.models import Account, Device, Message, Sim
from ownsms.tokens import new_device_token


@pytest.fixture
def device_auth(db):
    acc = Account.objects.create(email="a@b.uz")
    full, th = new_device_token()
    dev = Device.objects.create(account=acc, name="d", device_token=th, last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    return dev, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


@override_settings(OWNSMS={"POLL_TIMEOUT_SECONDS": 0})
@pytest.mark.django_db
def test_poll_returns_and_marks_dispatched(device_auth):
    dev, h = device_auth
    m = Message.objects.create(
        account=dev.account, device=dev, sim=dev.sims.first(), to="+998900000000", text="hi", status="queued"
    )
    r = Client().get("/api/v1/device/poll", **h)
    assert r.status_code == 200
    assert r.json()["jobs"][0]["id"] == m.id
    m.refresh_from_db()
    assert m.status == "dispatched"


@override_settings(OWNSMS={"POLL_TIMEOUT_SECONDS": 0})
@pytest.mark.django_db
def test_poll_empty_204(device_auth):
    _, h = device_auth
    assert Client().get("/api/v1/device/poll", **h).status_code == 204


@pytest.mark.django_db
def test_report_status(device_auth):
    dev, h = device_auth
    m = Message.objects.create(
        account=dev.account, device=dev, sim=dev.sims.first(), to="+998900000000", text="hi", status="dispatched"
    )
    r = Client().post(
        f"/api/v1/device/jobs/{m.id}/status", data=json.dumps({"status": "sent"}), content_type="application/json", **h
    )
    assert r.status_code == 200
    m.refresh_from_db()
    assert m.status == "sent"


@pytest.mark.django_db
def test_device_config(device_auth):
    dev, h = device_auth
    r = Client().get("/api/v1/device/config", **h)
    assert r.status_code == 200
    body = r.json()
    assert body["default_ttl"] == 86400
    assert body["sims"][0]["subscription_id"] == 1
    assert body["sims"][0]["rate_per_min"] == 15
    assert body["sims"][0]["jitter_max"] == 5
