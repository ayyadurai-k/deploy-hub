import pytest
from core.exceptions import IdentityLinkCollision
from django.contrib.auth import get_user_model
from oauth.models import GitHubProfile, GoogleProfile
from oauth.services.github import GitHubIdentity, GitHubTokens
from oauth.services.google import GoogleIdentity, GoogleTokens

from accounts.services import user_service
from accounts.services.jwt_service import issue_jwt_pair

User = get_user_model()


# -------- User model + manager --------

@pytest.mark.django_db
def test_create_user_lowercases_email_domain():
    u = User.objects.create_user(email="Alice@EXAMPLE.com")
    assert u.email == "Alice@example.com"


@pytest.mark.django_db
def test_create_user_without_password_is_unusable():
    u = User.objects.create_user(email="a@b.com")
    assert not u.has_usable_password()


@pytest.mark.django_db
def test_create_superuser_sets_flags():
    u = User.objects.create_superuser(email="root@x.com", password="x")
    assert u.is_staff and u.is_superuser


@pytest.mark.django_db
def test_create_superuser_rejects_non_staff():
    with pytest.raises(ValueError):
        User.objects.create_superuser(email="root@x.com", password="x", is_staff=False)


@pytest.mark.django_db
def test_user_str_is_email(user):
    assert str(user) == user.email


# -------- /auth/me --------

@pytest.mark.django_db
def test_me_returns_user_with_provider_flags(api_client, user):
    response = api_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["has_google"] is False
    assert body["has_github"] is False


@pytest.mark.django_db
def test_me_flags_reflect_linked_profiles(api_client, github_profile):
    response = api_client.get("/api/v1/auth/me")
    assert response.json()["has_github"] is True
    assert response.json()["has_google"] is False


@pytest.mark.django_db
def test_me_requires_auth(unauth_client):
    response = unauth_client.get("/api/v1/auth/me")
    assert response.status_code == 401


# -------- /auth/refresh + /auth/logout --------

@pytest.mark.django_db
def test_refresh_rotates_token(unauth_client, user):
    pair = issue_jwt_pair(user)
    unauth_client.cookies["refresh_token"] = pair.refresh
    response = unauth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert "access" in response.json()
    # New refresh cookie set
    assert unauth_client.cookies["refresh_token"].value != pair.refresh


@pytest.mark.django_db
def test_refresh_without_cookie_returns_401(unauth_client):
    response = unauth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "no_refresh_cookie"


@pytest.mark.django_db
def test_refresh_reuse_is_blocked(unauth_client, user):
    pair = issue_jwt_pair(user)
    unauth_client.cookies["refresh_token"] = pair.refresh
    unauth_client.post("/api/v1/auth/refresh")
    # Replay the old (now blacklisted) refresh token
    unauth_client.cookies["refresh_token"] = pair.refresh
    response = unauth_client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh"


@pytest.mark.django_db
def test_logout_clears_cookie(unauth_client, user):
    pair = issue_jwt_pair(user)
    unauth_client.cookies["refresh_token"] = pair.refresh
    response = unauth_client.post("/api/v1/auth/logout")
    assert response.status_code == 204


# -------- user_service.resolve_google --------

@pytest.mark.django_db
def test_resolve_google_creates_user_on_first_login():
    identity = GoogleIdentity(
        sub="g-1", email="new@example.com", email_verified=True,
        name="New User", picture="",
    )
    tokens = GoogleTokens(access_token="a", refresh_token="r", id_token="i", expires_in=3600, scope="openid")
    result = user_service.resolve_google(identity, tokens, current_user=None)
    assert result.user_created and result.profile_created
    assert result.user.email == "new@example.com"
    assert GoogleProfile.objects.filter(google_sub="g-1").exists()


@pytest.mark.django_db
def test_resolve_google_returning_user_is_idempotent():
    identity = GoogleIdentity(sub="g-2", email="x@x.com", email_verified=True, name="X", picture="")
    tokens = GoogleTokens(access_token="a", refresh_token="r", id_token="i", expires_in=3600, scope="openid")
    first = user_service.resolve_google(identity, tokens, current_user=None)
    second = user_service.resolve_google(identity, tokens, current_user=None)
    assert second.user.id == first.user.id
    assert not second.user_created and not second.profile_created


@pytest.mark.django_db
def test_resolve_google_link_collision_raises(user, other_user):
    identity = GoogleIdentity(sub="g-3", email=other_user.email, email_verified=True, name="", picture="")
    tokens = GoogleTokens(access_token="a", refresh_token="r", id_token="i", expires_in=3600, scope="openid")
    # other_user already has the profile
    user_service.resolve_google(identity, tokens, current_user=other_user)
    with pytest.raises(IdentityLinkCollision):
        user_service.resolve_google(identity, tokens, current_user=user)


# -------- user_service.resolve_github --------

@pytest.mark.django_db
def test_resolve_github_link_creates_profile_on_authed_user(user):
    identity = GitHubIdentity(user_id=99, login="alice", name="Alice", email=None, avatar_url="")
    tokens = GitHubTokens(access_token="a", scope="read:user repo", token_type="bearer")
    result = user_service.resolve_github(identity, tokens, current_user=user)
    assert result.profile_created and not result.user_created
    assert GitHubProfile.objects.filter(user=user, github_user_id=99).exists()


@pytest.mark.django_db
def test_resolve_github_login_without_email_raises():
    identity = GitHubIdentity(user_id=99, login="alice", name="", email=None, avatar_url="")
    tokens = GitHubTokens(access_token="a", scope="", token_type="bearer")
    from core.exceptions import OAuthError
    with pytest.raises(OAuthError):
        user_service.resolve_github(identity, tokens, current_user=None)


@pytest.mark.django_db
def test_resolve_github_collision(user, other_user):
    identity = GitHubIdentity(user_id=77, login="x", name="", email="x@y.com", avatar_url="")
    tokens = GitHubTokens(access_token="a", scope="", token_type="bearer")
    user_service.resolve_github(identity, tokens, current_user=user)
    with pytest.raises(IdentityLinkCollision):
        user_service.resolve_github(identity, tokens, current_user=other_user)
