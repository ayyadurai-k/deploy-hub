"""OAuth start + callback views.

OAUTH_FLOW.md §3/§6/§7 — login-only flow per the screening spec. The user
picks one provider on the login page; that sign-in resolves to a User (new
or existing by `(provider, provider_user_id)`). Two separate provider
sign-ins by the same human produce two separate User rows that happen to
share an email — by design (plan.md §2 + §6).

- GET  /api/v1/oauth/<provider>/start     anonymous browser nav → 302 to provider, sets state cookie
- GET  /api/v1/oauth/<provider>/callback  provider redirects browser here → verify state, exchange code, mint JWT, redirect SPA
"""
from typing import Literal
from urllib.parse import urlencode

from accounts.services import user_service
from accounts.services.jwt_service import issue_jwt_pair, set_refresh_cookie
from core.exceptions import OAuthError
from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework.permissions import AllowAny
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


# ---------- start views ----------

class _StartViewBase(APIView):
    permission_classes = [AllowAny]
    provider: Provider = "google"

    @staticmethod
    def _build_authorize_url(nonce: str) -> str:
        raise NotImplementedError

    def get(self, request):
        nonce, envelope = state_svc.issue_state(self.provider)
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
            state_svc.verify_state(echoed, envelope, self.provider)
        except ValueError as exc:
            response = _spa_redirect({"error": "oauth_state_invalid", "message": str(exc)})
            _clear_state_cookie(response)
            return response

        if not code:
            response = _spa_redirect({"error": "oauth_no_code", "message": "Authorization code missing"})
            _clear_state_cookie(response)
            return response

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

    def _exchange_and_resolve(self, code: str):
        raise NotImplementedError


class GoogleCallbackView(_CallbackViewBase):
    provider = "google"

    def _exchange_and_resolve(self, code):
        tokens = google_svc.exchange_code(code)
        identity = google_svc.verify_id_token(tokens.id_token)
        return user_service.resolve_google(identity, tokens)


class GitHubCallbackView(_CallbackViewBase):
    provider = "github"

    def _exchange_and_resolve(self, code):
        tokens = github_svc.exchange_code(code)
        identity = github_svc.fetch_identity(tokens.access_token)
        return user_service.resolve_github(identity, tokens)
        # NOTE: first-time GitHub sign-ins do NOT auto-sync repositories in this
        # request. Sync is purely manual via the dashboard's Sync button (per
        # plan.md §7). The original design ran sync inside the callback so the
        # dashboard would land populated, but with Supabase in us-east-1 and
        # this Lightsail in ap-south-1 the ~240 DB round-trips for 120 repos
        # blew past browser timeouts (~20–30 s), resulting in HTTP 499 from
        # nginx on first sign-in. Keeping the callback fast is the priority.
