import ipaddress

from django.utils import timezone

from .errors import ApiError
from .models import ApiKey, Device
from .tokens import hash_token


def bearer_from_request(request) -> str:
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        raise ApiError("unauthorized", "Missing Bearer token", 401)
    return header[len("Bearer ") :].strip()


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _ip_allowed(ip, allow):
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allow:
        try:
            if addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            if entry == ip:
                return True
    return False


def resolve_api_key(request, scope=None) -> ApiKey:
    token = bearer_from_request(request)
    try:
        key = ApiKey.objects.select_related("account", "device").get(key_hash=hash_token(token))
    except ApiKey.DoesNotExist:
        raise ApiError("unauthorized", "Invalid API key", 401)
    if key.revoked:
        raise ApiError("unauthorized", "API key revoked", 401)
    if scope and scope not in key.scopes:
        raise ApiError("forbidden", f"Key lacks scope '{scope}'", 403)
    if key.ip_allowlist:
        if not _ip_allowed(_client_ip(request), key.ip_allowlist):
            raise ApiError("ip_not_allowed", "Request IP is not in the allowlist", 403)
    ApiKey.objects.filter(pk=key.pk).update(last_used_at=timezone.now())
    return key


def resolve_device(request) -> Device:
    token = bearer_from_request(request)
    try:
        dev = Device.objects.select_related("account").get(device_token=hash_token(token))
    except Device.DoesNotExist:
        raise ApiError("unauthorized", "Invalid device token", 401)
    if dev.status != "active":
        raise ApiError("device_inactive", "Device is inactive", 403)
    return dev
