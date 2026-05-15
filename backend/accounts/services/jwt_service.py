from dataclasses import dataclass

from django.conf import settings
from django.http import HttpResponse
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


@dataclass(frozen=True)
class IssuedPair:
    access: str
    refresh: str


def issue_jwt_pair(user: User) -> IssuedPair:
    refresh = RefreshToken.for_user(user)
    return IssuedPair(access=str(refresh.access_token), refresh=str(refresh))


def set_refresh_cookie(response: HttpResponse, refresh_token: str) -> None:
    cfg = settings.REFRESH_COOKIE
    response.set_cookie(
        cfg["NAME"],
        refresh_token,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=cfg["PATH"],
        domain=cfg["DOMAIN"],
        secure=cfg["SECURE"],
        httponly=True,
        samesite=cfg["SAMESITE"],
    )


def clear_refresh_cookie(response: HttpResponse) -> None:
    cfg = settings.REFRESH_COOKIE
    response.delete_cookie(
        cfg["NAME"],
        path=cfg["PATH"],
        domain=cfg["DOMAIN"],
        samesite=cfg["SAMESITE"],
    )
