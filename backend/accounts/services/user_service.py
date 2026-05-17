"""User identity resolution for OAuth callbacks.

Encodes plan.md §2:
- Identity is keyed on (provider, provider_user_id), never email.
- No auto-merge by email.

Login-only — two independent sign-in paths, one per provider. Two same-email
sign-ins via different providers produce two separate User rows; the spec
doesn't ask for them to be linked.
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
