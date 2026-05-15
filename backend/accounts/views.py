from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.responses import error_response

from .serializers import UserSerializer
from .services.jwt_service import clear_refresh_cookie, set_refresh_cookie


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RefreshView(APIView):
    """Read the refresh token from the httpOnly cookie, rotate it, return a new access token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        cookie_name = settings.REFRESH_COOKIE["NAME"]
        raw = request.COOKIES.get(cookie_name)
        if not raw:
            return error_response(
                "no_refresh_cookie",
                "Refresh cookie missing",
                status.HTTP_401_UNAUTHORIZED,
            )

        try:
            old = RefreshToken(raw)
        except TokenError as exc:
            return error_response(
                "invalid_refresh",
                str(exc),
                status.HTTP_401_UNAUTHORIZED,
            )

        # SimpleJWT with ROTATE_REFRESH_TOKENS=True & BLACKLIST_AFTER_ROTATION=True:
        # blacklist the old, then mint a fresh pair.
        try:
            old.blacklist()
        except AttributeError:
            # Blacklist app not installed — fall back to no-op
            pass

        new_refresh = RefreshToken()
        # Copy the user-bound claims onto the new token
        for claim, value in old.payload.items():
            if claim in {"exp", "iat", "jti", "token_type"}:
                continue
            new_refresh[claim] = value

        access = str(new_refresh.access_token)
        refresh_str = str(new_refresh)

        response = Response({"access": access})
        set_refresh_cookie(response, refresh_str)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        cookie_name = settings.REFRESH_COOKIE["NAME"]
        raw = request.COOKIES.get(cookie_name)
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except (TokenError, AttributeError, InvalidToken):
                pass

        response = Response(status=status.HTTP_204_NO_CONTENT)
        clear_refresh_cookie(response)
        return response
