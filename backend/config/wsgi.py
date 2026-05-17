"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os
import socket

# Force IPv4-only DNS resolution. Azure Container Apps' Consumption plan has
# no IPv6 routing on egress; AAAA records returned for oauth2.googleapis.com,
# api.github.com, www.googleapis.com (JWKS), etc. resolve to addresses the
# kernel rejects with ENETUNREACH on connect(). Filter getaddrinfo down to
# A records so urllib3/requests only ever dials IPv4. Harmless under nginx
# + Lightsail (which has IPv6 disabled at the OS level anyway).
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(*args, **kwargs):
    return [r for r in _orig_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]


socket.getaddrinfo = _ipv4_only_getaddrinfo

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
