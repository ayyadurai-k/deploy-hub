"""OAuth start + callback views.

OAUTH_FLOW.md §3/§6/§7/§8.

Two flows live here:

- **Login flow** (anonymous):
    GET  /api/v1/oauth/<provider>/start            → 302 to provider
    GET  /api/v1/oauth/<provider>/callback         → exchange, resolve_*, mint JWT
- **Link flow** (authenticated, plan.md §2 — re-enabled 2026-05-17):
    POST /api/v1/oauth/<provider>/link-start       → JSON {authorize_url}, sets state cookie
    GET  /api/v1/oauth/<provider>/callback         → exchange, link_*, NO new JWT
"""
from typing import Literal
from urllib.parse import urlencode

from accounts.services import user_service
from accounts.services.jwt_service import issue_jwt_pair, set_refresh_cookie
from core.exceptions import OAuthError
from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from oauth.services import github as github_svc
from oauth.services import google as google_svc
from oauth.services import state as state_svc

Provider = Literal["google", "github"]


def _spa_redirect(query: dict[str, str]) -> HttpResponseRedirect:
    return HttpResponseRedirect(f"{settings.SPA_AUTH_COMPLETE_URL}#{urlencode(query)}")


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


# ---------- start views (login flow, anonymous browser nav) ----------

class _StartViewBase(APIView):
    permission_classes = [AllowAny]
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


# ---------- link-start views (link flow, authenticated XHR) ----------

class _LinkStartViewBase(APIView):
    """SPA hits this with Bearer auth; we set the state cookie via Set-Cookie
    and return the provider authorize URL in the JSON body. The SPA then does
    `window.location = authorize_url` to complete the redirect."""

    permission_classes = [IsAuthenticated]
    provider: Provider = "google"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        raise NotImplementedError

    def post(self, request):
        nonce, envelope = state_svc.issue_state(
            self.provider,
            intent="link",
            owner_user_id=request.user.id,
        )
        authorize_url = self._build_authorize_url(nonce)
        response = Response({"authorize_url": authorize_url})
        _set_state_cookie(response, envelope)
        return response


class GoogleLinkStartView(_LinkStartViewBase):
    provider = "google"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        return google_svc.build_authorize_url(nonce)


class GitHubLinkStartView(_LinkStartViewBase):
    provider = "github"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        return github_svc.build_authorize_url(nonce)


# ---------- callback views (handles both login + link via state.intent) ----------

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

        if payload.intent == "link":
            return self._handle_link(code, payload.owner_user_id)
        return self._handle_login(code)

    # --- login branch (anonymous flow — mints a JWT, sets refresh cookie) ---

    def _handle_login(self, code):
        try:
            result = self._exchange_and_resolve(code)
        except OAuthError as exc:
            response = _spa_redirect({"error": "oauth_error", "message": str(exc.detail)})
            _clear_state_cookie(response)
            return response
        except (google_svc.GoogleOAuthError, github_svc.GitHubOAuthError) as exc:
            response = _spa_redirect({"error": "oauth_provider_error", "message": str(exc)})
            _clear_state_cookie(response)
            return response

        pair = issue_jwt_pair(result.user)
        response = _spa_redirect({"access": pair.access, "intent": "login"})
        set_refresh_cookie(response, pair.refresh)
        _clear_state_cookie(response)
        return response

    # --- link branch (authenticated flow — NO new JWT) ---

    def _handle_link(self, code, owner_user_id):
        if owner_user_id is None:
            response = _spa_redirect({"error": "link_invalid", "message": "Link request missing owner"})
            _clear_state_cookie(response)
            return response
        try:
            self._exchange_and_link(code, owner_user_id)
        except OAuthError as exc:
            response = _spa_redirect({"error": "link_collision", "message": str(exc.detail)})
            _clear_state_cookie(response)
            return response
        except (google_svc.GoogleOAuthError, github_svc.GitHubOAuthError) as exc:
            response = _spa_redirect({"error": "oauth_provider_error", "message": str(exc)})
            _clear_state_cookie(response)
            return response

        response = _spa_redirect({"linked": self.provider, "intent": "link"})
        _clear_state_cookie(response)
        return response

    def _exchange_and_resolve(self, code: str):
        raise NotImplementedError

    def _exchange_and_link(self, code: str, owner_user_id: int):
        raise NotImplementedError


class GoogleCallbackView(_CallbackViewBase):
    provider = "google"

    def _exchange_and_resolve(self, code):
        tokens = google_svc.exchange_code(code)
        identity = google_svc.verify_id_token(tokens.id_token)
        return user_service.resolve_google(identity, tokens)

    def _exchange_and_link(self, code, owner_user_id):
        tokens = google_svc.exchange_code(code)
        identity = google_svc.verify_id_token(tokens.id_token)
        user_service.link_google(identity, tokens, owner_user_id)


class GitHubCallbackView(_CallbackViewBase):
    provider = "github"

    def _exchange_and_resolve(self, code):
        tokens = github_svc.exchange_code(code)
        identity = github_svc.fetch_identity(tokens.access_token)
        result = user_service.resolve_github(identity, tokens)
        # plan.md §7 — first-time GitHub connect triggers a synchronous sync so
        # the dashboard lands populated. Failures are captured on the profile
        # (last_sync_status=failure) and must not block login.
        if result.profile_created:
            self._try_sync(result.user.id)
        return result

    def _exchange_and_link(self, code, owner_user_id):
        tokens = github_svc.exchange_code(code)
        identity = github_svc.fetch_identity(tokens.access_token)
        created = user_service.link_github(identity, tokens, owner_user_id)
        if created:
            self._try_sync(owner_user_id)

    @staticmethod
    def _try_sync(user_id: int) -> None:
        import contextlib

        from repositories.services.github_sync import sync_repositories

        from oauth.models import GitHubProfile

        with contextlib.suppress(Exception):
            profile = GitHubProfile.objects.get(user_id=user_id)
            sync_repositories(profile)
