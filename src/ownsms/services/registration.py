import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..errors import ApiError
from ..models import Account, ApiKey, Device, PairingCode, Sim
from ..tokens import new_api_key, new_device_token
from . import audit


def _create_sims(device, sims):
    for s in sims or []:
        Sim.objects.create(
            device=device,
            subscription_id=s.get("subscription_id", 0),
            number=s.get("number", ""),
            operator=s.get("operator", ""),
            is_default=bool(s.get("is_default", False)),
        )


def _provision(account, device_name, app_version, sims):
    dev_full, dev_hash = new_device_token()
    device = Device.objects.create(
        account=account,
        name=device_name or "Device",
        device_token=dev_hash,
        app_version=app_version or "",
    )
    _create_sims(device, sims)
    key_full, prefix, key_hash = new_api_key()
    ApiKey.objects.create(account=account, device=device, key_hash=key_hash, prefix=prefix, scopes=["send", "read"])
    return {"account_id": account.id, "device_id": device.id, "device_token": dev_full, "api_key": key_full}


@transaction.atomic
def register(*, email="", device_name="", app_version="", sims=None):
    account = Account.objects.create(email=email or "")
    result = _provision(account, device_name, app_version, sims)
    device = Device.objects.get(pk=result["device_id"])
    audit.log(account, "system", "account.registered", f"device:{device.id}")
    return result


@transaction.atomic
def create_pairing_code(account, ttl_seconds=600):
    code = secrets.token_hex(16)  # 32 hex chars (fits max_length=32)
    pc = PairingCode.objects.create(
        account=account, code=code, expires_at=timezone.now() + timedelta(seconds=ttl_seconds), used=False
    )
    return {"code": code, "expires_at": pc.expires_at.isoformat()}


@transaction.atomic
def pair(*, code, device_name="", app_version="", sims=None):
    pc = PairingCode.objects.select_for_update().filter(code=code, used=False).first()
    if not pc or pc.expires_at <= timezone.now():
        raise ApiError("invalid_code", "Invalid or expired pairing code", 400)
    pc.used = True
    pc.save(update_fields=["used"])
    result = _provision(pc.account, device_name, app_version, sims)
    device = Device.objects.get(pk=result["device_id"])
    audit.log(pc.account, "device", "device.paired", f"device:{device.id}")
    return result
