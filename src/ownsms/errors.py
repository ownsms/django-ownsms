from django.http import JsonResponse


class ApiError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def error_response(err: "ApiError") -> JsonResponse:
    return JsonResponse({"error": {"code": err.code, "message": err.message}}, status=err.status)
