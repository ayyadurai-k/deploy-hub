"""User identity resolution for OAuth callbacks.

Encodes plan.md §2:
- Identity is keyed on (provider, provider_user_id), never email.
- No auto-merge by email.

Two entry points per provider:
- resolve_*   — anonymous login flow. Creates a new User if no existing profile.
- link_*      — authenticated link flow. Attaches a new profile to an existing
                User, refuses cross-user collisions. Returns True if a new
                profile was created (callers may want to trigger a first-sync).
"""
from dataclasses import dataclass

from core.exceptions import OAuthError
from django.db import transaction
from oauth.models import GitHubProfile, GoogleProfile
from oauth.services.github import GitHubIdentity, GitHubTokens
from oauth.services.google import GoogleIdentity, GoogleTokens

from accounts.models import User


@dataclass(frozen=True)
class ResolutionResult:
    user: User
    profile_created: bool
    user_created: bool


@transaction.atomic
def resolve_google(identity: GoogleIdentity, tokens: GoogleTokens) -> ResolutionResult:
    existing = GoogleProfile.objects.select_related("user").filter(google_sub=identity.sub).first()

    if existing is not None:
        existing.email = identity.email or existing.email
        existing.picture_url = identity.picture or existing.picture_url
        existing.set_access_token(tokens.access_token)
        existing.save()
        if identity.email and existing.user.email != identity.email:
            existing.user.email = identity.email
            existing.user.save(update_fields=["email"])
        return ResolutionResult(user=existing.user, profile_created=False, user_created=False)

    user = User.objects.create_user(email=identity.email, display_name=identity.name or "")
    profile = GoogleProfile(
        user=user,
        google_sub=identity.sub,
        email=identity.email,
        picture_url=identity.picture,
    )
    profile.set_access_token(tokens.access_token)
    profile.save()
    return ResolutionResult(user=user, profile_created=True, user_created=True)


@transaction.atomic
def resolve_github(identity: GitHubIdentity, tokens: GitHubTokens) -> ResolutionResult:
    existing = GitHubProfile.objects.select_related("user").filter(github_user_id=identity.user_id).first()

    if existing is not None:
        existing.set_access_token(tokens.access_token)
        existing.github_login = identity.login or existing.github_login
        existing.avatar_url = identity.avatar_url or existing.avatar_url
        existing.save()
        if identity.email and existing.user.email != identity.email:
            existing.user.email = identity.email
            existing.user.save(update_fields=["email"])
        return ResolutionResult(user=existing.user, profile_created=False, user_created=False)

    # New user. GitHub login requires a verified email; refuse otherwise so the
    # user can either make their primary email public or sign in via Google.
    if not identity.email:
        raise OAuthError("GitHub account has no verified primary email")

    user = User.objects.create_user(
        email=identity.email,
        display_name=identity.name or identity.login,
    )
    profile = GitHubProfile(
        user=user,
        github_user_id=identity.user_id,
        github_login=identity.login,
        avatar_url=identity.avatar_url,
    )
    profile.set_access_token(tokens.access_token)
    profile.save()
    return ResolutionResult(user=user, profile_created=True, user_created=True)


# ─── Link flow (authenticated user attaches a new provider) ──────────────

@transaction.atomic
def link_google(identity: GoogleIdentity, tokens: GoogleTokens, owner_user_id: int) -> bool:
    """Attach a GoogleProfile to the user identified by owner_user_id.

    Returns True if a new profile was created, False if an existing profile
    was refreshed. Raises OAuthError on cross-user collision.
    """
    existing = GoogleProfile.objects.filter(google_sub=identity.sub).first()
    if existing is not None:
        if existing.user_id != owner_user_id:
            raise OAuthError("This Google account is linked to another user")
        # Same user re-running the link flow — refresh stored token + profile.
        existing.email = identity.email or existing.email
        existing.picture_url = identity.picture or existing.picture_url
        existing.set_access_token(tokens.access_token)
        existing.save()
        return False

    if GoogleProfile.objects.filter(user_id=owner_user_id).exists():
        raise OAuthError("This account already has a Google profile attached")

    profile = GoogleProfile(
        user_id=owner_user_id,
        google_sub=identity.sub,
        email=identity.email,
        picture_url=identity.picture,
    )
    profile.set_access_token(tokens.access_token)
    profile.save()
    return True


@transaction.atomic
def link_github(identity: GitHubIdentity, tokens: GitHubTokens, owner_user_id: int) -> bool:
    """Attach a GitHubProfile to the user identified by owner_user_id.

    Returns True if a new profile was created, False if an existing profile
    was refreshed. Raises OAuthError on cross-user collision.
    """
    existing = GitHubProfile.objects.filter(github_user_id=identity.user_id).first()
    if existing is not None:
        if existing.user_id != owner_user_id:
            raise OAuthError("This GitHub account is linked to another user")
        existing.github_login = identity.login or existing.github_login
        existing.avatar_url = identity.avatar_url or existing.avatar_url
        existing.set_access_token(tokens.access_token)
        existing.save()
        return False

    if GitHubProfile.objects.filter(user_id=owner_user_id).exists():
        raise OAuthError("This account already has a GitHub profile attached")

    profile = GitHubProfile(
        user_id=owner_user_id,
        github_user_id=identity.user_id,
        github_login=identity.login,
        avatar_url=identity.avatar_url,
    )
    profile.set_access_token(tokens.access_token)
    profile.save()
    return True
