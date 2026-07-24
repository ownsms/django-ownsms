import pytest
from django.test import Client, RequestFactory
from django.utils import timezone

from ownsms.auth import resolve_api_key
from ownsms.errors import ApiError
from ownsms.models import Account, ApiKey, AuditLog, Device, Sim
from ownsms.tokens import new_api_key


def _key(ip_allowlist=None, is_test=False):
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t", last_seen_at=timezone.now())
    Sim.objects.create(device=dev, subscription_id=1, number="+998901112233", is_default=True)
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(
        account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send", "read"], ip_allowlist=ip_allowlist or []
    )
    return acc, dev, full


@pytest.mark.django_db
def test_ip_allowlist_blocks_and_allows():
    acc, dev, full = _key(ip_allowlist=["10.0.0.0/8"])
    rf = RequestFactory()
    blocked = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {full}", REMOTE_ADDR="8.8.8.8")
    with pytest.raises(ApiError) as e:
        resolve_api_key(blocked, scope="read")
    assert e.value.status == 403
    ok = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {full}", REMOTE_ADDR="10.1.2.3")
    assert resolve_api_key(ok, scope="read") is not None


@pytest.mark.django_db
def test_spoofed_xff_does_not_satisfy_allowlist():
    # nginx sets X-Real-IP to the real peer and X-Forwarded-For is client-controllable.
    acc, dev, full = _key(ip_allowlist=["10.0.0.0/8"])
    rf = RequestFactory()
    spoofed = rf.get(
        "/", HTTP_AUTHORIZATION=f"Bearer {full}", REMOTE_ADDR="8.8.8.8", HTTP_X_FORWARDED_FOR="10.1.2.3, 8.8.8.8"
    )
    with pytest.raises(ApiError) as e:
        resolve_api_key(spoofed, scope="read")
    assert e.value.status == 403
    # nginx-set X-Real-IP is authoritative: an allowed peer passes even with a hostile REMOTE_ADDR fallback.
    ok = rf.get("/", HTTP_AUTHORIZATION=f"Bearer {full}", REMOTE_ADDR="8.8.8.8", HTTP_X_REAL_IP="10.1.2.3")
    assert resolve_api_key(ok, scope="read") is not None


@pytest.mark.django_db
def test_register_writes_audit_and_endpoint_reads_it():
    c = Client()
    r = c.post("/api/v1/register", data="{}", content_type="application/json")
    token = r.json()["device_token"]
    assert AuditLog.objects.filter(action="account.registered").count() == 1
    # read via api key — make one
    from ownsms.models import Account, Device

    acc = Account.objects.first()
    dev = Device.objects.first()
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["read"])
    g = c.get("/api/v1/audit", HTTP_AUTHORIZATION=f"Bearer {full}")
    assert g.status_code == 200 and len(g.json()["data"]) >= 1


@pytest.mark.django_db
def test_admin_registers_models():
    from django.contrib import admin

    import ownsms.admin  # noqa: F401
    from ownsms import models

    assert admin.site.is_registered(models.Account)
    assert admin.site.is_registered(models.Message)
