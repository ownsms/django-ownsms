import json

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.models import Account, ApiKey, Campaign, Device, Message, Sim
from ownsms.tokens import new_api_key


@pytest.fixture
def key_header(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    return dev, {"HTTP_AUTHORIZATION": f"Bearer {full}"}


def _post(h, key):
    return Client().post(
        "/api/v1/campaigns",
        data=json.dumps(
            {
                "text": "Salom",
                "recipients": [{"to": "901110001"}, {"to": "901110002"}],
                "idempotency_key": key,
            }
        ),
        content_type="application/json",
        **h,
    )


@pytest.mark.django_db
def test_same_key_returns_first_campaign_no_double_send(key_header):
    dev, h = key_header
    r1 = _post(h, "k1")
    r2 = _post(h, "k1")
    assert r1.status_code == 202 and r2.status_code == 202, (r1.content, r2.content)
    assert r1.json()["id"] == r2.json()["id"]
    assert Campaign.objects.count() == 1
    assert Message.objects.count() == 2  # not doubled


@pytest.mark.django_db
def test_different_keys_create_two_campaigns(key_header):
    dev, h = key_header
    r1 = _post(h, "k1")
    r2 = _post(h, "k2")
    assert r1.json()["id"] != r2.json()["id"]
    assert Campaign.objects.count() == 2
    assert Message.objects.count() == 4


@pytest.mark.django_db
def test_no_key_never_collides(key_header):
    dev, h = key_header
    # Empty/absent key must store NULL, not "", so keyless campaigns never collide on the constraint.
    r1 = _post(h, "")
    r2 = _post(h, "")
    assert r1.status_code == 202 and r2.status_code == 202, (r1.content, r2.content)
    assert Campaign.objects.count() == 2
    assert Campaign.objects.filter(idempotency_key__isnull=True).count() == 2
