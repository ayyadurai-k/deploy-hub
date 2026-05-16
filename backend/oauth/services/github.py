"""GitHub OAuth service.

OAUTH_FLOW.md §5 — GitHub OAuth Apps do not implement OIDC, so we obtain the
access token and then call /user (and /user/emails when needed) to learn who
the user is.
"""
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from django.conf import settings

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"


@dataclass(frozen=True)
class GitHubTokens:
    access_token: str


@dataclass(frozen=True)
class GitHubIdentity:
    user_id: int
    login: str
    name: str
    email: str | None
    avatar_url: str


class GitHubOAuthError(RuntimeError):
    pass


def build_authorize_url(state: str) -> str:
    cfg = settings.GITHUB_OAUTH
    params = {
        "client_id": cfg["CLIENT_ID"],
        "redirect_uri": cfg["REDIRECT_URI"],
        "scope": " ".join(cfg["SCOPES"]),
        "state": state,
        "allow_signup": "true",
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> GitHubTokens:
    cfg = settings.GITHUB_OAUTH
    response = requests.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": cfg["CLIENT_ID"],
            "client_secret": cfg["CLIENT_SECRET"],
            "code": code,
            "redirect_uri": cfg["REDIRECT_URI"],
        },
        headers={"Accept": "application/json"},
        timeout=15,
    )
    if response.status_code >= 400:
        raise GitHubOAuthError(f"token exchange failed: {response.status_code} {response.text}")
    body = response.json()
    if "error" in body:
        raise GitHubOAuthError(f"token exchange error: {body.get('error_description') or body['error']}")
    return GitHubTokens(access_token=body["access_token"])


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "repo-manage-backend",
    }


def fetch_identity(access_token: str) -> GitHubIdentity:
    response = requests.get("https://api.github.com/user", headers=_headers(access_token), timeout=10)
    if response.status_code >= 400:
        raise GitHubOAuthError(f"/user fetch failed: {response.status_code} {response.text}")
    body: dict[str, Any] = response.json()

    email = body.get("email")
    if not email:
        # email is hidden by default — fetch verified primary from /user/emails
        emails_resp = requests.get(
            "https://api.github.com/user/emails", headers=_headers(access_token), timeout=10
        )
        if emails_resp.status_code < 400:
            for entry in emails_resp.json():
                if entry.get("primary") and entry.get("verified"):
                    email = entry.get("email")
                    break

    return GitHubIdentity(
        user_id=int(body["id"]),
        login=str(body.get("login", "")),
        name=str(body.get("name") or ""),
        email=email or None,
        avatar_url=str(body.get("avatar_url", "")),
    )
