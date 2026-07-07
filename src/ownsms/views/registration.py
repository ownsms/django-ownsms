import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import resolve_device
from ..errors import ApiError, error_response
from ..services import registration


def _body(request):
    return json.loads(request.body or "{}")


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    try:
        b = _body(request)
        return JsonResponse(
            registration.register(
                email=b.get("email", ""),
                device_name=b.get("device_name", ""),
                app_version=b.get("app_version", ""),
                sims=b.get("sims"),
            ),
            status=201,
        )
    except ApiError as e:
        return error_response(e)
    except (ValueError, json.JSONDecodeError):
        return error_response(ApiError("bad_request", "Invalid JSON", 400))


@csrf_exempt
@require_http_methods(["POST"])
def pair(request):
    try:
        b = _body(request)
        return JsonResponse(
            registration.pair(
                code=b.get("code", ""),
                device_name=b.get("device_name", ""),
                app_version=b.get("app_version", ""),
                sims=b.get("sims"),
            ),
            status=201,
        )
    except ApiError as e:
        return error_response(e)
    except (ValueError, json.JSONDecodeError):
        return error_response(ApiError("bad_request", "Invalid JSON", 400))


@csrf_exempt
@require_http_methods(["POST"])
def pairing_code(request):
    try:
        dev = resolve_device(request)
        return JsonResponse(registration.create_pairing_code(dev.account), status=201)
    except ApiError as e:
        return error_response(e)
