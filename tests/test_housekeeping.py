from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from ownsms.models import Account, Device, Message, Sim


@pytest.mark.django_db
def test_housekeeping_command():
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t")
    sim = Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    old = timezone.now() - timedelta(seconds=10)
    m = Message.objects.create(account=acc, device=dev, sim=sim, to="+998900000000", text="hi", status="queued", ttl=1)
    Message.objects.filter(pk=m.pk).update(created_at=old)
    out = StringIO()
    call_command("ownsms_housekeeping", stdout=out)
    m.refresh_from_db()
    assert m.status == "expired"
    assert "expired=1" in out.getvalue()
