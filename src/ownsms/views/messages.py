import json

from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import resolve_api_key
from ..errors import ApiError, error_response
from ..models import Message
from ..services import messaging

# The internal handoff state "dispatched" (message handed to the device) is presented as
# "sending" in the public API, so developers see a clean lifecycle:
# queued → sending → sent → delivered | failed | expired | canceled.
# "sent" = accepted by the carrier (the practical success state); "delivered" is a bonus that
# only arrives if the mobile operator returns a delivery report.
_PUBLIC_STATUS = {"dispatched": "sending"}


def _to_public_status(status: str) -> str:
    return _PUBLIC_STATUS.get(status, status)


def _to_internal_status(status: str) -> str:
    return "dispatched" if status == "sending" else status


def _serialize(m: Message):
    return {
        "id": f"msg_{m.id}",
        "status": _to_public_status(m.status),
        "to": m.to,
        "text": m.text,
        "from": m.sim.number if m.sim else None,
        "segments": m.segments,
        "error_code": m.error_code or None,
        "created_at": m.created_at.isoformat(),
    }


def _msg_pk(raw: str):
    return int(raw[4:]) if raw.startswith("msg_") else int(raw)


@csrf_exempt
@require_http_methods(["POST", "GET"])
def messages(request):
    try:
        if request.method == "POST":
            key = resolve_api_key(request, scope="send")
            body = json.loads(request.body or "{}")
            msg, _ = messaging.create_message(
                key,
                to=body.get("to", ""),
                text=body.get("text", ""),
                from_=body.get("from"),
                queued=bool(body.get("queued", False)),
                ttl=body.get("ttl"),
                idempotency_key=body.get("idempotency_key", ""),
                callback_url=body.get("callback_url", ""),
                send_at=parse_datetime(body["send_at"]) if body.get("send_at") else None,
            )
            return JsonResponse(_serialize(msg), status=202)
        key = resolve_api_key(request, scope="read")
        qs = Message.objects.filter(account=key.account).order_by("-id")
        status = request.GET.get("status")
        if status:
            qs = qs.filter(status=_to_internal_status(status))
        campaign_id = request.GET.get("campaign_id")
        if campaign_id:
            raw = campaign_id[5:] if campaign_id.startswith("camp_") else campaign_id
            qs = qs.filter(campaign_id=int(raw)) if raw.isdigit() else qs.none()
        before = request.GET.get("before")
        if before and before.isdigit():
            qs = qs.filter(id__lt=int(before))
        try:
            limit = min(max(int(request.GET.get("limit", 50)), 1), 200)
        except ValueError:
            limit = 50
        items = list(qs[:limit])
        next_before = items[-1].id if len(items) == limit else None
        return JsonResponse({"data": [_serialize(m) for m in items], "next_before": next_before})
    except ApiError as e:
        return error_response(e)
    except (ValueError, json.JSONDecodeError):
        return error_response(ApiError("bad_request", "Invalid JSON body", 400))


@csrf_exempt
@require_http_methods(["GET"])
def message_detail(request, mid):
    try:
        key = resolve_api_key(request, scope="read")
        try:
            pk = _msg_pk(mid)
        except ValueError:
            return error_response(ApiError("not_found", "Message not found", 404))
        m = Message.objects.filter(account=key.account, pk=pk).first()
        if not m:
            return error_response(ApiError("not_found", "Message not found", 404))
        return JsonResponse(_serialize(m))
    except ApiError as e:
        return error_response(e)


@csrf_exempt
@require_http_methods(["POST"])
def message_cancel(request, mid):
    try:
        key = resolve_api_key(request, scope="send")
        try:
            pk = _msg_pk(mid)
        except ValueError:
            return error_response(ApiError("not_found", "Message not found", 404))
        m = Message.objects.filter(account=key.account, pk=pk).first()
        if not m:
            return error_response(ApiError("not_found", "Message not found", 404))
        if m.status != "queued":
            return error_response(ApiError("cannot_cancel", "Only queued messages can be canceled", 409))
        m.status = "canceled"
        m.save(update_fields=["status"])
        return JsonResponse(_serialize(m))
    except ApiError as e:
        return error_response(e)
