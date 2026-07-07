from datetime import timedelta

import pytest
from django.utils import timezone

from ownsms.models import Account, ApiKey, Device, Message, Sim


@pytest.mark.django_db
def test_relationships_and_online():
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="A52", device_token="x", last_seen_at=timezone.now())
    sim = Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", operator="beeline", is_default=True)
    key = ApiKey.objects.create(account=acc, device=dev, key_hash="h", prefix="osk_ab12")
    msg = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="queued")
    assert msg.device.account == acc
    assert dev.is_online(timezone.now())
    dev.last_seen_at = timezone.now() - timedelta(minutes=5)
    assert not dev.is_online(timezone.now())
