from typing import Any

from rest_framework.response import Response


def error_response(code: str, message: str, status_code: int, detail: Any = None) -> Response:
    payload: dict[str, Any] = {"error": {"code": code, "message": message}}
    if detail is not None:
        payload["error"]["detail"] = detail
    return Response(payload, status=status_code)
