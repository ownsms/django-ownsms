from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..auth import resolve_api_key
from ..errors import ApiError, error_response
from ..models import AuditLog


@csrf_exempt
@require_http_methods(["GET"])
def audit(request):
    try:
        key = resolve_api_key(request, scope="read")
        rows = AuditLog.objects.filter(account=key.account).order_by("-id")[:100]
        return JsonResponse(
            {
                "data": [
                    {
                        "actor": r.actor,
                        "action": r.action,
                        "target": r.target,
                        "ip": r.ip,
                        "at": r.created_at.isoformat(),
                    }
                    for r in rows
                ]
            }
        )
    except ApiError as e:
        return error_response(e)
