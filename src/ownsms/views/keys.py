import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import _client_ip, resolve_api_key
from ..errors import ApiError, error_response
from ..models import ApiKey, Device
from ..services import audit
from ..tokens import new_api_key


def _serialize(k):
    return {
        "id": k.id,
        "prefix": k.prefix,
        "name": k.name,
        "scopes": k.scopes,
        "device_id": k.device_id,
        "ip_allowlist": k.ip_allowlist,
        "is_test": k.is_test,
        "revoked": k.revoked,
        "created_at": k.created_at.isoformat(),
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
    }


@csrf_exempt
@require_http_methods(["GET", "POST"])
def keys(request):
    try:
        if request.method == "POST":
            key = resolve_api_key(request, scope="send")
            b = json.loads(request.body or "{}")
            device_id = b.get("device_id")
            device = Device.objects.filter(account=key.account, pk=device_id).first() if device_id else key.device
            if not device:
                raise ApiError("invalid_device", "device_id is required and must be your device", 422)
            scopes = b.get("scopes") or ["send", "read"]
            # A key can never mint another key with scopes beyond its own.
            if not set(scopes).issubset(key.scopes):
                raise ApiError("forbidden", "Cannot grant scopes beyond your own", 403)
            full, prefix, key_hash = new_api_key()
            k = ApiKey.objects.create(
                account=key.account,
                device=device,
                key_hash=key_hash,
                prefix=prefix,
                name=b.get("name", ""),
                scopes=scopes,
                ip_allowlist=b.get("ip_allowlist") or [],
                is_test=bool(b.get("is_test", False)),
            )
            audit.log(key.account, "key", "apikey.created", f"key:{k.id}", _client_ip(request))
            return JsonResponse({**_serialize(k), "api_key": full}, status=201)
        key = resolve_api_key(request)
        return JsonResponse({"data": [_serialize(k) for k in key.account.api_keys.order_by("-id")]})
    except ApiError as e:
        return error_response(e)
    except (ValueError, json.JSONDecodeError):
        return error_response(ApiError("bad_request", "Invalid JSON", 400))


@csrf_exempt
@require_http_methods(["POST"])
def key_revoke(request, kid):
    try:
        key = resolve_api_key(request, scope="send")
        try:
            pk = int(kid)
        except ValueError:
            return error_response(ApiError("not_found", "Key not found", 404))
        k = ApiKey.objects.filter(account=key.account, pk=pk).first()
        if not k:
            return error_response(ApiError("not_found", "Key not found", 404))
        k.revoked = True
        k.save(update_fields=["revoked"])
        audit.log(key.account, "key", "apikey.revoked", f"key:{k.id}", _client_ip(request))
        return JsonResponse(_serialize(k))
    except ApiError as e:
        return error_response(e)
