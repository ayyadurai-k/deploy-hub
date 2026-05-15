"""Google OIDC service.

OAUTH_FLOW.md §4 — Google issues a signed id_token alongside the access token.
We verify the signature against Google's JWKS and read identity claims directly,
no /userinfo HTTP call needed.
"""
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError
from django.conf import settings


GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}

# Identity-only (plan.md §1). openid is the OIDC trigger.
GOOGLE_SCOPES = ["openid", "email", "profile"]


@dataclass(frozen=True)
class GoogleTokens:
    access_token: str
    refresh_token: str | None
    id_token: str
    expires_in: int
    scope: str


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str
    picture: str


class GoogleOAuthError(RuntimeError):
    pass


def build_authorize_url(state: str) -> str:
    cfg = settings.GOOGLE_OAUTH
    params = {
        "client_id": cfg["CLIENT_ID"],
        "redirect_uri": cfg["REDIRECT_URI"],
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",  # request a refresh_token
        "prompt": "consent",       # ensure refresh_token comes back on re-consent
        "include_granted_scopes": "true",
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(code: str) -> GoogleTokens:
    cfg = settings.GOOGLE_OAUTH
    response = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": cfg["CLIENT_ID"],
            "client_secret": cfg["CLIENT_SECRET"],
            "redirect_uri": cfg["REDIRECT_URI"],
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if response.status_code >= 400:
        raise GoogleOAuthError(f"token exchange failed: {response.status_code} {response.text}")
    body = response.json()
    return GoogleTokens(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        id_token=body["id_token"],
        expires_in=int(body.get("expires_in", 3600)),
        scope=body.get("scope", ""),
    )


_jwks_cache: dict[str, Any] = {"keys": None}


def _load_jwks() -> Any:
    if _jwks_cache["keys"] is None:
        response = requests.get(GOOGLE_JWKS_URL, timeout=10)
        response.raise_for_status()
        _jwks_cache["keys"] = JsonWebKey.import_key_set(response.json())
    return _jwks_cache["keys"]


def verify_id_token(id_token: str) -> GoogleIdentity:
    cfg = settings.GOOGLE_OAUTH
    try:
        claims = jwt.decode(id_token, key=_load_jwks())
        claims.validate()
    except JoseError as exc:
        raise GoogleOAuthError(f"id_token verify failed: {exc}") from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleOAuthError(f"unexpected iss: {claims.get('iss')}")
    if claims.get("aud") != cfg["CLIENT_ID"]:
        raise GoogleOAuthError("aud mismatch")

    return GoogleIdentity(
        sub=str(claims["sub"]),
        email=str(claims.get("email", "")),
        email_verified=bool(claims.get("email_verified", False)),
        name=str(claims.get("name", "")),
        picture=str(claims.get("picture", "")),
    )
