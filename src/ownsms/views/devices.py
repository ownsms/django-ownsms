from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import _client_ip, resolve_api_key
from ..errors import ApiError, error_response
from ..models import Device
from ..services import audit


def _serialize(d, now):
    return {
        "id": d.id,
        "name": d.name,
        "status": d.status,
        "online": d.is_online(now),
        "last_seen": d.last_seen_at.isoformat() if d.last_seen_at else None,
        "app_version": d.app_version,
        "sims": [
            {
                "number": s.number,
                "operator": s.operator,
                "is_default": s.is_default,
                "subscription_id": s.subscription_id,
            }
            for s in d.sims.all()
        ],
    }


@csrf_exempt
@require_http_methods(["GET"])
def devices(request):
    try:
        key = resolve_api_key(request)
        now = timezone.now()
        return JsonResponse({"data": [_serialize(d, now) for d in key.account.devices.order_by("id")]})
    except ApiError as e:
        return error_response(e)


@csrf_exempt
@require_http_methods(["POST"])
def device_action(request, did, act):
    try:
        key = resolve_api_key(request, scope="send")
        try:
            pk = int(did)
        except ValueError:
            return error_response(ApiError("not_found", "Device not found", 404))
        d = Device.objects.filter(account=key.account, pk=pk).first()
        if not d:
            return error_response(ApiError("not_found", "Device not found", 404))
        if act == "deactivate":
            d.status = "inactive"
        elif act == "activate":
            d.status = "active"
        else:
            return error_response(ApiError("bad_action", f"Unknown action {act}", 400))
        d.save(update_fields=["status"])
        audit.log(key.account, "key", f"device.{act}d", f"device:{d.id}", _client_ip(request))
        return JsonResponse(_serialize(d, timezone.now()))
    except ApiError as e:
        return error_response(e)
