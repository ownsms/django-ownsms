import json

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import resolve_api_key
from ..errors import ApiError, error_response
from ..models import Campaign
from ..services import campaigns
from ..views.messages import _serialize as _serialize_message  # reuse


@csrf_exempt
@require_http_methods(["POST"])
def create(request):
    try:
        key = resolve_api_key(request, scope="send")
        b = json.loads(request.body or "{}")
        send_at = None
        if b.get("send_at"):
            send_at = parse_datetime(b["send_at"])
            if send_at is None or timezone.is_naive(send_at):
                raise ApiError("invalid_send_at", "send_at must be an ISO-8601 datetime with timezone", 422)
        c = campaigns.create_campaign(
            key,
            text=b.get("text", ""),
            recipients=b.get("recipients", []),
            from_=b.get("from"),
            send_at=send_at,
            queued=bool(b.get("queued", True)),
            rotate_sims=bool(b.get("rotate_sims", False)),
            callback_url=b.get("callback_url", ""),
            idempotency_key=b.get("idempotency_key", ""),
        )
        return JsonResponse({"id": f"camp_{c.id}", "status": c.status, "total": c.total}, status=202)
    except campaigns.CampaignValidation as e:
        return JsonResponse(
            {"error": {"code": "validation_error", "message": "Some recipients are invalid", "bad_rows": e.bad}},
            status=422,
        )
    except ApiError as e:
        return error_response(e)
    except (ValueError, json.JSONDecodeError):
        return error_response(ApiError("bad_request", "Invalid JSON", 400))


def _camp_pk(raw):
    return int(raw[5:]) if raw.startswith("camp_") else int(raw)


@csrf_exempt
@require_http_methods(["GET"])
def detail(request, cid):
    try:
        key = resolve_api_key(request, scope="read")
        c = Campaign.objects.filter(account=key.account, pk=_camp_pk(cid)).first()
        if not c:
            return error_response(ApiError("not_found", "Campaign not found", 404))
        campaigns._maybe_complete(c)
        return JsonResponse(
            {"id": f"camp_{c.id}", "status": c.status, "total": c.total, "progress": campaigns.progress(c)}
        )
    except (ValueError, ApiError) as e:
        if isinstance(e, ApiError):
            return error_response(e)
        return error_response(ApiError("not_found", "Campaign not found", 404))


@csrf_exempt
@require_http_methods(["GET"])
def messages(request, cid):
    try:
        key = resolve_api_key(request, scope="read")
        c = Campaign.objects.filter(account=key.account, pk=_camp_pk(cid)).first()
        if not c:
            return error_response(ApiError("not_found", "Campaign not found", 404))
        # Match the shared MessageList contract + the sibling /messages endpoint: newest-first,
        # `before` is an exclusive upper-bound id, cursor field is `next_before`.
        qs = c.messages.select_related("sim").order_by("-id")
        before = request.GET.get("before")
        if before and before.isdigit():
            qs = qs.filter(id__lt=int(before))
        try:
            limit = min(max(int(request.GET.get("limit", 50)), 1), 200)
        except ValueError:
            limit = 50
        items = list(qs[:limit])
        next_before = items[-1].id if len(items) == limit else None
        return JsonResponse({"data": [_serialize_message(m) for m in items], "next_before": next_before})
    except ApiError as e:
        return error_response(e)
    except ValueError:
        return error_response(ApiError("not_found", "Campaign not found", 404))


@csrf_exempt
@require_http_methods(["POST"])
def action(request, cid, act):
    try:
        key = resolve_api_key(request, scope="send")
        c = Campaign.objects.filter(account=key.account, pk=_camp_pk(cid)).first()
        if not c:
            return error_response(ApiError("not_found", "Campaign not found", 404))
        campaigns.control(c, act)
        return JsonResponse({"id": f"camp_{c.id}", "status": c.status, "total": c.total})
    except ApiError as e:
        return error_response(e)
    except ValueError:
        return error_response(ApiError("not_found", "Campaign not found", 404))
