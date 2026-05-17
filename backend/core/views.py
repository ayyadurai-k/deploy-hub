import socket
import time

import requests
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


@api_view(["GET"])
@permission_classes([AllowAny])
def egress_diag(_request):
    """Smoke-test outbound network access from this pod. Hit each target
    over HTTPS with a 5s timeout and report status code or exception. Used
    once to confirm whether the deploy platform restricts egress; remove
    after diagnostics are done."""
    targets = [
        "https://1.1.1.1",                    # Cloudflare anycast — generic public IPv4
        "https://api.github.com/zen",         # GitHub API
        "https://github.com/robots.txt",      # GitHub web
        "https://oauth2.googleapis.com/",     # Google token endpoint host
        "https://www.googleapis.com/",        # Google JWKS / userinfo host
        "https://accounts.google.com/.well-known/openid-configuration",
    ]
    results = []
    for url in targets:
        host = url.split("/")[2]
        entry: dict = {"url": url}
        try:
            entry["resolved_a"] = [
                ai[4][0]
                for ai in socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)
            ][:3]
        except Exception as e:
            entry["resolved_a"] = f"{type(e).__name__}: {e}"
        t = time.time()
        try:
            r = requests.get(url, timeout=5, allow_redirects=False)
            entry["http"] = r.status_code
        except Exception as e:
            entry["http"] = f"{type(e).__name__}: {str(e)[:200]}"
        entry["elapsed_ms"] = int((time.time() - t) * 1000)
        results.append(entry)
    return Response({"targets": results})
