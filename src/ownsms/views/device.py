import json
import time

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .. import conf
from ..auth import resolve_device
from ..errors import ApiError, error_response
from ..models import Device, Message
from ..services import dispatch


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    try:
        dev = resolve_device(request)
        body = json.loads(request.body or "{}")
        dev.app_version = body.get("app_version", dev.app_version)
        dev.last_seen_at = timezone.now()
        dev.save(update_fields=["app_version", "last_seen_at"])
        return JsonResponse({"device_id": dev.id})
    except ApiError as e:
        return error_response(e)


@csrf_exempt
@require_http_methods(["GET"])
def poll(request):
    try:
        dev = resolve_device(request)
    except ApiError as e:
        return error_response(e)
    deadline = time.monotonic() + conf.get("POLL_TIMEOUT_SECONDS")
    # Mark the device online once per poll, not every second: a poll lasts <= POLL_TIMEOUT
    # (< DEVICE_ONLINE_SECONDS) and the device immediately re-polls, so last_seen stays fresh
    # while we drop ~30 redundant writes per poll cycle per device.
    Device.objects.filter(pk=dev.pk).update(last_seen_at=timezone.now())
    while True:
        jobs = dispatch.claim_jobs(dev, timezone.now())
        if jobs:
            return JsonResponse(
                {
                    "jobs": [
                        {
                            "id": j.id,
                            "to": j.to,
                            "text": j.text,
                            "subscription_id": j.sim.subscription_id if j.sim else None,
                            "segments": j.segments,
                        }
                        for j in jobs
                    ]
                }
            )
        if time.monotonic() >= deadline:
            return HttpResponse(status=204)
        time.sleep(conf.get("POLL_INTERVAL_SECONDS"))


@csrf_exempt
@require_http_methods(["POST"])
def job_status(request, mid):
    try:
        dev = resolve_device(request)
        body = json.loads(request.body or "{}")
        try:
            pk = int(mid)
        except ValueError:
            return error_response(ApiError("not_found", "Job not found", 404))
        m = dispatch.report_status(dev, pk, body.get("status", ""), body.get("error_code", ""))
        return JsonResponse({"id": m.id, "status": m.status})
    except ApiError as e:
        return error_response(e)


@csrf_exempt
@require_http_methods(["POST"])
def heartbeat(request):
    try:
        dev = resolve_device(request)
        Device.objects.filter(pk=dev.pk).update(last_seen_at=timezone.now())
        return JsonResponse({"ok": True})
    except ApiError as e:
        return error_response(e)


@csrf_exempt
@require_http_methods(["GET"])
def device_config(request):
    from .. import conf

    try:
        dev = resolve_device(request)
    except ApiError as e:
        return error_response(e)
    sims = [
        {
            "subscription_id": s.subscription_id,
            "number": s.number,
            "is_default": s.is_default,
            "rate_per_min": s.rate_per_min,
            "rate_per_hour": s.rate_per_hour,
            "rate_per_day": s.rate_per_day,
            "jitter_min": s.jitter_min,
            "jitter_max": s.jitter_max,
            "work_hours_start": s.work_hours_start.isoformat() if s.work_hours_start else None,
            "work_hours_end": s.work_hours_end.isoformat() if s.work_hours_end else None,
            "daily_quota": s.daily_quota,
        }
        for s in dev.sims.all()
    ]
    return JsonResponse({"default_ttl": conf.get("DEFAULT_TTL_SECONDS"), "sims": sims})


@csrf_exempt
@require_http_methods(["GET"])
def device_status(request):
    from ..auth import resolve_api_key

    try:
        key = resolve_api_key(request, scope="read")
    except ApiError as e:
        return error_response(e)
    dev = key.device
    now = timezone.now()
    today_sent = Message.objects.filter(device=dev, sent_at__date=timezone.localdate()).count()
    return JsonResponse(
        {
            "online": dev.is_online(now),
            "status": dev.status,
            "last_seen": dev.last_seen_at.isoformat() if dev.last_seen_at else None,
            "today_sent": today_sent,
            "sims": [{"number": s.number, "operator": s.operator, "is_default": s.is_default} for s in dev.sims.all()],
        }
    )
