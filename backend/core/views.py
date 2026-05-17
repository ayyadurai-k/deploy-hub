import json
import socket
import time
import traceback

from django.db import OperationalError, connections
from django.http import HttpResponse, JsonResponse
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


def diag_ping(_request):
    """Plain Django view, no DRF, no middleware-heavy machinery — confirms
    URL routing and process liveness without any rendering surprises."""
    return JsonResponse({"pong": True, "python": True})


def diag_egress(_request):
    """Outbound reachability test. Plain Django (not DRF) so we never hit
    BrowsableAPIRenderer or content-negotiation pitfalls. Always returns
    JSON — top-level try/except guarantees we never 500."""
    try:
        # Defer the import so requests being missing/broken can't fail
        # the URL conf load.
        import requests  # noqa: PLC0415

        targets = [
            "https://1.1.1.1",
            "https://api.github.com/zen",
            "https://github.com/robots.txt",
            "https://oauth2.googleapis.com/",
            "https://www.googleapis.com/",
            "https://accounts.google.com/.well-known/openid-configuration",
        ]
        results = []
        for url in targets:
            host = url.split("/")[2]
            entry = {"url": url}

            try:
                addrs = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
                entry["resolved_a"] = [a[4][0] for a in addrs][:3]
            except Exception as e:
                entry["resolved_a_error"] = f"{type(e).__name__}: {e}"

            t0 = time.time()
            try:
                r = requests.get(url, timeout=5, allow_redirects=False, verify=False)
                entry["http"] = r.status_code
            except Exception as e:
                entry["http_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            entry["elapsed_ms"] = int((time.time() - t0) * 1000)

            results.append(entry)

        return JsonResponse({"targets": results}, json_dumps_params={"indent": 2})
    except Exception as e:
        return HttpResponse(
            json.dumps({"diag_error": f"{type(e).__name__}: {e}",
                        "traceback": traceback.format_exc()},
                       indent=2),
            content_type="application/json",
            status=200,
        )
