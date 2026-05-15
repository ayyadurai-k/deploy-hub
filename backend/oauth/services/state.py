"""Signed, short-lived OAuth state tokens.

OAUTH_FLOW.md §3 — the `state` parameter is OAuth's CSRF defense. We generate
a random value at /start, store its signed envelope in a SameSite=Lax cookie,
echo the raw value through the provider, then verify both match at /callback.

Envelope also carries the *intent* (login vs. link) and (for link) the owning
user_id, so the callback knows which branch to take without a second lookup.
"""
import secrets
from dataclasses import dataclass
from typing import Any, Literal

from django.conf import settings
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner


Intent = Literal["login", "link"]

_SIGNER_SALT = "oauth.state.v1"


@dataclass(frozen=True)
class StatePayload:
    nonce: str
    provider: str
    intent: Intent
    owner_user_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.nonce,
            "p": self.provider,
            "i": self.intent,
            "u": self.owner_user_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StatePayload":
        return cls(
            nonce=data["n"],
            provider=data["p"],
            intent=data["i"],
            owner_user_id=data.get("u"),
        )


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=_SIGNER_SALT)


def issue_state(provider: str, intent: Intent, owner_user_id: int | None = None) -> tuple[str, str]:
    """Return (nonce_echoed_through_provider, signed_envelope_to_set_as_cookie)."""
    payload = StatePayload(
        nonce=secrets.token_urlsafe(32),
        provider=provider,
        intent=intent,
        owner_user_id=owner_user_id,
    )
    import json
    envelope = _signer().sign(json.dumps(payload.to_dict(), separators=(",", ":")))
    return payload.nonce, envelope


def verify_state(echoed_nonce: str, signed_envelope: str, expected_provider: str) -> StatePayload:
    """Raise ValueError on any mismatch. Returns the decoded payload on success."""
    import json
    if not echoed_nonce or not signed_envelope:
        raise ValueError("missing state")
    ttl = settings.OAUTH_STATE_COOKIE["TTL_SECONDS"]
    try:
        raw = _signer().unsign(signed_envelope, max_age=ttl)
    except SignatureExpired as exc:
        raise ValueError(f"state expired: {exc}") from exc
    except BadSignature as exc:
        raise ValueError(f"state signature invalid: {exc}") from exc
    payload = StatePayload.from_dict(json.loads(raw))
    if payload.provider != expected_provider:
        raise ValueError("state provider mismatch")
    if not secrets.compare_digest(payload.nonce, echoed_nonce):
        raise ValueError("state nonce mismatch")
    return payload
