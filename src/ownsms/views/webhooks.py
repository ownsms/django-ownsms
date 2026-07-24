import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import _client_ip, resolve_api_key
from ..errors import ApiError, error_response
from ..models import WebhookDelivery
from ..services import audit, webhooks


def _serialize(wh):
    return {"url": wh.url, "events": wh.events, "enabled": wh.enabled, "secret": wh.secret}


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def webhook(request):
    try:
        key = resolve_api_key(request)  # any valid key for the account
        wh = webhooks.get_or_create_config(key.account)
        if request.method == "PUT":
            b = json.loads(request.body or "{}")
            if "url" in b:
                wh.url = b["url"] or ""
            if "events" in b:
                wh.events = b["events"] or []
            if "enabled" in b:
                wh.enabled = bool(b["enabled"])
            wh.save(update_fields=["url", "events", "enabled"])
            audit.log(key.account, "key", "webhook.updated", "", _client_ip(request))
        return JsonResponse(_serialize(wh))
    except ApiError as e:
        return error_response(e)
    except (ValueError, json.JSONDecodeError):
        return error_response(ApiError("bad_request", "Invalid JSON", 400))


@csrf_exempt
@require_http_methods(["GET"])
def deliveries(request):
    try:
        key = resolve_api_key(request, scope="read")
        qs = WebhookDelivery.objects.filter(account=key.account).order_by("-id")
        before = request.GET.get("before")
        if before and before.isdigit():
            qs = qs.filter(id__lt=int(before))
        items = list(qs[:50])
        return JsonResponse(
            {
                "data": [
                    {
                        "id": d.id,
                        "event": d.event,
                        "status": d.status,
                        "attempts": d.attempts,
                        "url": d.url,
                        "created_at": d.created_at.isoformat(),
                    }
                    for d in items
                ],
                "next_before": items[-1].id if len(items) == 50 else None,
            }
        )
    except ApiError as e:
        return error_response(e)
