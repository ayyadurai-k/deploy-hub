"""User identity resolution for OAuth callbacks.

Encodes plan.md §2:
- Identity is keyed on (provider, provider_user_id), never email.
- No auto-merge by email.
- Linking happens only from an authenticated session (current_user provided).
- Collision: provider account already attached to a *different* User → 409.

The functions here are intentionally side-effecting: they upsert profile rows
and persist encrypted provider tokens. The caller (an OAuth callback view) owns
the transaction boundary and the JWT issuance.
"""
from dataclasses import dataclass
from datetime import timedelta

from core.exceptions import IdentityLinkCollision
from django.db import transaction
from django.utils import timezone
from oauth.models import GitHubProfile, GoogleProfile
from oauth.services.github import GitHubIdentity, GitHubTokens
from oauth.services.google import GoogleIdentity, GoogleTokens

from accounts.models import User


@dataclass(frozen=True)
class ResolutionResult:
    user: User
    profile_created: bool
    user_created: bool


def _split_scopes(scope_str: str) -> list[str]:
    return [s for s in scope_str.replace(",", " ").split() if s]


@transaction.atomic
def resolve_google(
    identity: GoogleIdentity,
    tokens: GoogleTokens,
    current_user: User | None,
) -> ResolutionResult:
    existing = GoogleProfile.objects.select_related("user").filter(google_sub=identity.sub).first()

    if current_user is not None:
        # Link intent.
        if existing is None:
            profile = GoogleProfile(
                user=current_user,
                google_sub=identity.sub,
                email=identity.email,
                picture_url=identity.picture,
            )
            _apply_google_tokens(profile, identity, tokens)
            profile.save()
            return ResolutionResult(user=current_user, profile_created=True, user_created=False)
        if existing.user_id == current_user.id:
            # Same user re-linking — refresh stored tokens, no-op identity-wise.
            _apply_google_tokens(existing, identity, tokens)
            existing.save()
            return ResolutionResult(user=current_user, profile_created=False, user_created=False)
        raise IdentityLinkCollision()

    # Login intent.
    if existing is not None:
        _apply_google_tokens(existing, identity, tokens)
        existing.save()
        # Keep email in sync with provider's latest verified value.
        if identity.email and existing.user.email != identity.email:
            existing.user.email = identity.email
            existing.user.save(update_fields=["email"])
        return ResolutionResult(user=existing.user, profile_created=False, user_created=False)

    user = User.objects.create_user(
        email=identity.email,
        display_name=identity.name or "",
    )
    profile = GoogleProfile(
        user=user,
        google_sub=identity.sub,
        email=identity.email,
        picture_url=identity.picture,
    )
    _apply_google_tokens(profile, identity, tokens)
    profile.save()
    return ResolutionResult(user=user, profile_created=True, user_created=True)


def _apply_google_tokens(profile: GoogleProfile, identity: GoogleIdentity, tokens: GoogleTokens) -> None:
    profile.email = identity.email or profile.email
    profile.picture_url = identity.picture or profile.picture_url
    profile.set_access_token(tokens.access_token)
    if tokens.refresh_token:
        profile.set_refresh_token(tokens.refresh_token)
    profile.token_expires_at = timezone.now() + timedelta(seconds=tokens.expires_in)
    profile.scopes = _split_scopes(tokens.scope)


@transaction.atomic
def resolve_github(
    identity: GitHubIdentity,
    tokens: GitHubTokens,
    current_user: User | None,
) -> ResolutionResult:
    existing = GitHubProfile.objects.select_related("user").filter(github_user_id=identity.user_id).first()

    if current_user is not None:
        if existing is None:
            profile = GitHubProfile(
                user=current_user,
                github_user_id=identity.user_id,
                github_login=identity.login,
                avatar_url=identity.avatar_url,
            )
            _apply_github_tokens(profile, tokens)
            profile.save()
            return ResolutionResult(user=current_user, profile_created=True, user_created=False)
        if existing.user_id == current_user.id:
            _apply_github_tokens(existing, tokens)
            existing.github_login = identity.login or existing.github_login
            existing.avatar_url = identity.avatar_url or existing.avatar_url
            existing.save()
            return ResolutionResult(user=current_user, profile_created=False, user_created=False)
        raise IdentityLinkCollision()

    if existing is not None:
        _apply_github_tokens(existing, tokens)
        existing.github_login = identity.login or existing.github_login
        existing.avatar_url = identity.avatar_url or existing.avatar_url
        existing.save()
        if identity.email and existing.user.email != identity.email:
            existing.user.email = identity.email
            existing.user.save(update_fields=["email"])
        return ResolutionResult(user=existing.user, profile_created=False, user_created=False)

    # New user. GitHub email can be null; fall back to a synthesized handle
    # only if absolutely necessary — login flow requires an email.
    email = identity.email
    if not email:
        # No verified email — refuse to create a new account. Caller should
        # surface this as a user-facing error and prompt the user to either
        # make a GitHub email public or sign up via Google first.
        from core.exceptions import OAuthError
        raise OAuthError("GitHub account has no verified primary email")

    user = User.objects.create_user(
        email=email,
        display_name=identity.name or identity.login,
    )
    profile = GitHubProfile(
        user=user,
        github_user_id=identity.user_id,
        github_login=identity.login,
        avatar_url=identity.avatar_url,
    )
    _apply_github_tokens(profile, tokens)
    profile.save()
    return ResolutionResult(user=user, profile_created=True, user_created=True)


def _apply_github_tokens(profile: GitHubProfile, tokens: GitHubTokens) -> None:
    profile.set_access_token(tokens.access_token)
    profile.scopes = _split_scopes(tokens.scope)
