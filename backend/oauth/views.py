"""OAuth start + callback views.

OAUTH_FLOW.md §3/§6/§7/§8 — flow is documented there. This module is the HTTP
glue between `oauth.services.{state,google,github}` and `accounts.services.{
user_service,jwt_service}`.

Two start verbs per provider:
- GET  /api/v1/oauth/<provider>/start  — login flow. Anonymous browser nav. 302
  to provider. Sets state cookie with intent=login.
- POST /api/v1/oauth/<provider>/start  — link flow. Authenticated XHR from SPA.
  Returns { authorize_url } and sets state cookie with intent=link.

One callback verb:
- GET  /api/v1/oauth/<provider>/callback — provider redirects browser here.
  Verifies state cookie, exchanges code, resolves identity, issues JWT (login)
  or just redirects (link). Cleans up state cookie.
"""
from typing import Literal
from urllib.parse import urlencode

from accounts.services import user_service
from accounts.services.jwt_service import issue_jwt_pair, set_refresh_cookie
from core.exceptions import IdentityLinkCollision, OAuthError
from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from oauth.services import github as github_svc
from oauth.services import google as google_svc
from oauth.services import state as state_svc

Provider = Literal["google", "github"]


def _spa_redirect(query: dict[str, str]) -> HttpResponseRedirect:
    base = settings.SPA_AUTH_COMPLETE_URL
    return HttpResponseRedirect(f"{base}#{urlencode(query)}")


def _set_state_cookie(response, envelope: str) -> None:
    cfg = settings.OAUTH_STATE_COOKIE
    response.set_cookie(
        cfg["NAME"],
        envelope,
        max_age=cfg["TTL_SECONDS"],
        path=cfg["PATH"],
        secure=cfg["SECURE"],
        httponly=True,
        samesite=cfg["SAMESITE"],
    )


def _clear_state_cookie(response) -> None:
    cfg = settings.OAUTH_STATE_COOKIE
    response.delete_cookie(cfg["NAME"], path=cfg["PATH"], samesite=cfg["SAMESITE"])


# ---------- start views ----------

class _StartViewBase(APIView):
    """Login = GET (anonymous, browser nav). Link = POST (authenticated XHR)."""

    permission_classes = [AllowAny]
    authentication_classes = [JWTAuthentication]
    provider: Provider = "google"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        raise NotImplementedError

    def get(self, request):
        nonce, envelope = state_svc.issue_state(self.provider, intent="login")
        authorize_url = self._build_authorize_url(nonce)
        response = HttpResponseRedirect(authorize_url)
        _set_state_cookie(response, envelope)
        return response

    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"error": {"code": "not_authenticated", "message": "Authentication required to link"}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        nonce, envelope = state_svc.issue_state(
            self.provider, intent="link", owner_user_id=request.user.id,
        )
        authorize_url = self._build_authorize_url(nonce)
        response = Response({"authorize_url": authorize_url})
        _set_state_cookie(response, envelope)
        return response


class GoogleStartView(_StartViewBase):
    provider = "google"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        return google_svc.build_authorize_url(nonce)


class GitHubStartView(_StartViewBase):
    provider = "github"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        return github_svc.build_authorize_url(nonce)


# ---------- callback views ----------

class _CallbackViewBase(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    provider: Provider = "google"

    def get(self, request):
        code = request.GET.get("code", "")
        echoed = request.GET.get("state", "")
        envelope = request.COOKIES.get(settings.OAUTH_STATE_COOKIE["NAME"], "")

        try:
            payload = state_svc.verify_state(echoed, envelope, self.provider)
        except ValueError as exc:
            response = _spa_redirect({"error": "oauth_state_invalid", "message": str(exc)})
            _clear_state_cookie(response)
            return response

        if not code:
            response = _spa_redirect({"error": "oauth_no_code", "message": "Authorization code missing"})
            _clear_state_cookie(response)
            return response

        current_user = None
        if payload.intent == "link":
            from accounts.models import User
            current_user = User.objects.filter(pk=payload.owner_user_id).first()
            if current_user is None:
                response = _spa_redirect({"error": "link_owner_missing", "message": "Session not found"})
                _clear_state_cookie(response)
                return response

        try:
            result = self._exchange_and_resolve(code, current_user)
        except IdentityLinkCollision:
            response = _spa_redirect({
                "error": "link_collision",
                "message": f"This {self.provider} account is already linked to another user",
            })
            _clear_state_cookie(response)
            return response
        except OAuthError as exc:
            response = _spa_redirect({"error": "oauth_error", "message": str(exc.detail)})
            _clear_state_cookie(response)
            return response
        except (google_svc.GoogleOAuthError, github_svc.GitHubOAuthError) as exc:
            response = _spa_redirect({"error": "oauth_provider_error", "message": str(exc)})
            _clear_state_cookie(response)
            return response

        if payload.intent == "login":
            pair = issue_jwt_pair(result.user)
            response = _spa_redirect({"access": pair.access, "intent": "login"})
            set_refresh_cookie(response, pair.refresh)
        else:
            response = _spa_redirect({"linked": self.provider, "intent": "link"})

        _clear_state_cookie(response)
        return response

    def _exchange_and_resolve(self, code: str, current_user):
        raise NotImplementedError


class GoogleCallbackView(_CallbackViewBase):
    provider = "google"

    def _exchange_and_resolve(self, code, current_user):
        tokens = google_svc.exchange_code(code)
        identity = google_svc.verify_id_token(tokens.id_token)
        return user_service.resolve_google(identity, tokens, current_user)


class GitHubCallbackView(_CallbackViewBase):
    provider = "github"

    def _exchange_and_resolve(self, code, current_user):
        tokens = github_svc.exchange_code(code)
        identity = github_svc.fetch_identity(tokens.access_token)
        result = user_service.resolve_github(identity, tokens, current_user)
        # plan.md §7 — first-time GitHub connect triggers a synchronous sync so
        # the SPA dashboard lands populated. Failures are captured on the
        # profile (last_sync_status=failure) and do not break login.
        if result.profile_created:
            import contextlib

            from repositories.services.github_sync import sync_repositories

            # Sync failure must not block login — last_sync_status on the profile
            # carries the error state instead.
            with contextlib.suppress(Exception):
                sync_repositories(result.user.github_profile)
        return result
