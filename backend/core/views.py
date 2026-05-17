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
    """Outbound reachability test. Raw TCP SYN to port 443 with a 2-second
    timeout per target — no HTTP, no TLS, no requests library — so a wholly
    unreachable network resolves in ~16s for 8 targets, comfortably inside
    any worker timeout. Returns plain JSON, never 500s."""
    try:
        targets = [
            ("1.1.1.1", 443),
            ("api.github.com", 443),
            ("github.com", 443),
            ("oauth2.googleapis.com", 443),
            ("www.googleapis.com", 443),
            ("accounts.google.com", 443),
        ]
        results = []
        for host, port in targets:
            entry = {"host": host, "port": port}

            try:
                addrs = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
                entry["resolved_a"] = [a[4][0] for a in addrs][:3]
            except Exception as e:
                entry["resolved_a_error"] = f"{type(e).__name__}: {e}"
                results.append(entry)
                continue

            t0 = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            try:
                s.connect((entry["resolved_a"][0], port))
                entry["tcp"] = "ok"
            except Exception as e:
                entry["tcp_error"] = f"{type(e).__name__}: {e}"
            finally:
                s.close()
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
