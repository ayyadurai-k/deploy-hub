from typing import Any

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler


class GitHubNotConnected(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "GitHub account not connected"
    default_code = "github_not_connected"


class OAuthError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "OAuth handshake failed"
    default_code = "oauth_error"


def _classify(exc, response) -> str:
    code = getattr(exc, "default_code", None) or getattr(exc, "code", None)
    if code:
        return str(code)
    mapping = {
        400: "bad_request",
        401: "not_authenticated",
        403: "permission_denied",
        404: "not_found",
        405: "method_not_allowed",
        406: "not_acceptable",
        409: "conflict",
        415: "unsupported_media_type",
        429: "throttled",
    }
    return mapping.get(response.status_code, "error")


def custom_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    if (isinstance(detail, dict) and set(detail.keys()) == {"detail"}) or (isinstance(detail, dict) and "detail" in detail and len(detail) == 1):
        message = str(detail["detail"])
        payload_detail = None
    elif isinstance(detail, (list, dict)):
        message = "Request validation failed"
        payload_detail = detail
    else:
        message = str(detail)
        payload_detail = None

    code = _classify(exc, response)
    error: dict[str, Any] = {"code": code, "message": message}
    if payload_detail is not None:
        error["detail"] = payload_detail
    response.data = {"error": error}
    return response
