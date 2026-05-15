"""Shared pytest fixtures for the backend test suite.

`api_client` and `unauth_client` are the standard handles for HTTP tests.
`*_user` fixtures pre-create user + profile rows for OAuth-dependent tests.
"""
import pytest
from accounts.models import User
from accounts.services.jwt_service import issue_jwt_pair
from oauth.models import GitHubProfile, GoogleProfile, SyncStatus
from rest_framework.test import APIClient


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(email="alice@example.com", display_name="Alice")


@pytest.fixture
def other_user(db) -> User:
    return User.objects.create_user(email="bob@example.com", display_name="Bob")


@pytest.fixture
def google_profile(user: User) -> GoogleProfile:
    profile = GoogleProfile(
        user=user,
        google_sub="goog-sub-1",
        email=user.email,
        picture_url="https://example.com/alice.png",
    )
    profile.set_access_token("google-access-token")
    profile.set_refresh_token("google-refresh-token")
    profile.scopes = ["openid", "email", "profile"]
    profile.save()
    return profile


@pytest.fixture
def github_profile(user: User) -> GitHubProfile:
    profile = GitHubProfile(
        user=user,
        github_user_id=4242,
        github_login="alice",
        avatar_url="https://example.com/alice.png",
        last_sync_status=SyncStatus.PENDING,
    )
    profile.set_access_token("github-access-token")
    profile.scopes = ["read:user", "repo"]
    profile.save()
    return profile


@pytest.fixture
def unauth_client() -> APIClient:
    client = APIClient(HTTP_HOST="localhost")
    return client


@pytest.fixture
def api_client(user: User) -> APIClient:
    client = APIClient(HTTP_HOST="localhost")
    pair = issue_jwt_pair(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.access}")
    return client


@pytest.fixture
def other_api_client(other_user: User) -> APIClient:
    client = APIClient(HTTP_HOST="localhost")
    pair = issue_jwt_pair(other_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {pair.access}")
    return client
