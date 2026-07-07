import pytest
from django.test import RequestFactory

from ownsms.auth import resolve_api_key, resolve_device
from ownsms.errors import ApiError
from ownsms.models import Account, ApiKey, Device
from ownsms.tokens import new_api_key, new_device_token


@pytest.mark.django_db
def test_resolve_api_key_ok_and_scope():
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t")
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send"])
    rf = RequestFactory()
    req = rf.post("/", HTTP_AUTHORIZATION=f"Bearer {full}")
    key = resolve_api_key(req, scope="send")
    assert key.device == dev
    with pytest.raises(ApiError) as e:
        resolve_api_key(req, scope="read")
    assert e.value.status == 403


@pytest.mark.django_db
def test_resolve_api_key_revoked():
    acc = Account.objects.create(email="a@b.uz")
    dev = Device.objects.create(account=acc, name="d", device_token="t")
    full, prefix, kh = new_api_key()
    ApiKey.objects.create(account=acc, device=dev, key_hash=kh, prefix=prefix, scopes=["send"], revoked=True)
    req = RequestFactory().post("/", HTTP_AUTHORIZATION=f"Bearer {full}")
    with pytest.raises(ApiError) as e:
        resolve_api_key(req, scope="send")
    assert e.value.status == 401


@pytest.mark.django_db
def test_resolve_device_ok():
    acc = Account.objects.create(email="a@b.uz")
    full, th = new_device_token()
    dev = Device.objects.create(account=acc, name="d", device_token=th, status="active")
    req = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {full}")
    assert resolve_device(req) == dev


@pytest.mark.django_db
def test_resolve_device_inactive():
    acc = Account.objects.create(email="a@b.uz")
    full, th = new_device_token()
    Device.objects.create(account=acc, name="d", device_token=th, status="inactive")
    req = RequestFactory().get("/", HTTP_AUTHORIZATION=f"Bearer {full}")
    with pytest.raises(ApiError) as e:
        resolve_device(req)
    assert e.value.status == 403
    assert e.value.code == "device_inactive"
