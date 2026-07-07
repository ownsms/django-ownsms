import pytest
from django.utils import timezone

from ownsms.errors import ApiError
from ownsms.models import Account, ApiKey, Device, Message, Sim
from ownsms.services.messaging import create_message


@pytest.fixture
def key(db):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", operator="x", is_default=True)
    return ApiKey.objects.create(account=acc, device=dev, key_hash="h", prefix="osk_a", scopes=["send", "read"])


@pytest.mark.django_db
def test_create_immediate_uses_default_sim(key):
    msg, created = create_message(key, to="901110000", text="hi")
    assert created and msg.status == "queued"
    assert msg.to == "+998901110000"
    assert msg.sim.is_default and msg.segments == 1


@pytest.mark.django_db
def test_immediate_offline_rejected(key):
    key.device.last_seen_at = None
    key.device.save()
    with pytest.raises(ApiError) as e:
        create_message(key, to="901110000", text="hi", queued=False)
    assert e.value.code == "device_offline" and e.value.status == 409


@pytest.mark.django_db
def test_idempotency_returns_same(key):
    a, c1 = create_message(key, to="901110000", text="hi", idempotency_key="k1")
    b, c2 = create_message(key, to="901110000", text="hi", idempotency_key="k1")
    assert c1 and not c2 and a.id == b.id


@pytest.mark.django_db
def test_idempotency_conflict_on_different_payload(key):
    create_message(key, to="901110000", text="hi", idempotency_key="k1")
    with pytest.raises(ApiError) as e:
        create_message(key, to="901110000", text="DIFFERENT", idempotency_key="k1")
    assert e.value.code == "idempotency_conflict"


@pytest.mark.django_db
def test_idempotency_race_returns_existing(key):
    """Simulate a race: another worker already created the row; create_message must return it."""
    sim = key.device.sims.filter(is_default=True).first()
    existing = Message.objects.create(
        account=key.account,
        device=key.device,
        sim=sim,
        to="+998901110000",
        text="hi",
        status="queued",
        queued=True,
        ttl=86400,
        segments=1,
        idempotency_key="kX",
    )
    result, created = create_message(key, to="901110000", text="hi", idempotency_key="kX")
    assert not created
    assert result.id == existing.id
