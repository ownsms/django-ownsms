import json

import pytest
from django.test import Client
from django.utils import timezone

from ownsms.errors import ApiError
from ownsms.models import Account, ApiKey, Device, Message, Sim
from ownsms.services.messaging import create_message
from ownsms.tokens import new_api_key


@pytest.fixture
def ctx(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    key = ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"])
    header = {"HTTP_AUTHORIZATION": f"Bearer {full}"}
    return acc, dev, key, header


@pytest.mark.django_db
def test_cancel_dispatched_returns_409(ctx):
    acc, dev, key, header = ctx
    msg, _ = create_message(key, to="901110000", text="hi", queued=True)
    Message.objects.filter(pk=msg.id).update(status="dispatched")  # device already picked it up
    r = Client().post(f"/api/v1/messages/msg_{msg.id}/cancel", **header)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "cannot_cancel"
    assert Message.objects.get(pk=msg.id).status == "dispatched"  # not clobbered


@pytest.mark.django_db
def test_invalid_send_at_rejected(ctx):
    acc, dev, key, header = ctx
    r = Client().post(
        "/api/v1/messages",
        data=json.dumps({"to": "901110000", "text": "hi", "queued": True, "send_at": "tomorrow"}),
        content_type="application/json",
        **header,
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "bad_request"
    assert Message.objects.count() == 0  # nothing queued


@pytest.mark.django_db
def test_empty_text_rejected(ctx):
    acc, dev, key, header = ctx
    with pytest.raises(ApiError) as e:
        create_message(key, to="901110000", text="   ")
    assert e.value.code == "invalid_text" and e.value.status == 422


@pytest.mark.django_db
def test_non_string_text_rejected(ctx):
    acc, dev, key, header = ctx
    with pytest.raises(ApiError) as e:
        create_message(key, to="901110000", text=None)
    assert e.value.code == "invalid_text" and e.value.status == 422
