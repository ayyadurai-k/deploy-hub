from django.db import OperationalError, connections
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def healthz(_request):
    return Response({"status": "ok"})


@api_view(["GET"])
@permission_classes([AllowAny])
def readyz(_request):
    try:
        connections["default"].cursor().execute("SELECT 1")
    except OperationalError as exc:
        return Response(
            {"status": "not_ready", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ready"})
