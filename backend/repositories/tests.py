from unittest.mock import patch

import pytest
from oauth.models import SyncStatus

from repositories.models import Repository
from repositories.services.github_sync import sync_repositories

# -------- list endpoint --------

@pytest.mark.django_db
def test_list_without_github_profile_returns_409(api_client):
    response = api_client.get("/api/v1/repositories/")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "github_not_connected"


@pytest.mark.django_db
def test_list_with_github_profile_returns_paginated(api_client, github_profile):
    response = api_client.get("/api/v1/repositories/")
    assert response.status_code == 200
    body = response.json()
    assert body == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.django_db
def test_list_requires_auth(unauth_client):
    response = unauth_client.get("/api/v1/repositories/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_excludes_other_users_repos(api_client, github_profile, other_user):
    # Make a profile + repo for the other user
    from oauth.models import GitHubProfile
    other = GitHubProfile(user=other_user, github_user_id=999, github_login="bob")
    other.set_access_token("x")
    other.save()
    Repository.objects.create(
        github_profile=other,
        github_repo_id=1,
        name="bob-repo",
        full_name="bob/bob-repo",
        html_url="http://x",
    )
    # And one for alice
    Repository.objects.create(
        github_profile=github_profile,
        github_repo_id=2,
        name="alice-repo",
        full_name="alice/alice-repo",
        html_url="http://x",
    )
    response = api_client.get("/api/v1/repositories/")
    body = response.json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "alice-repo"


# -------- sync service --------

_FAKE_REPOS = [
    {
        "id": 100,
        "name": "alpha",
        "full_name": "alice/alpha",
        "private": False,
        "default_branch": "main",
        "description": "first",
        "html_url": "https://github.com/alice/alpha",
        "created_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2024-06-01T00:00:00Z",
    },
    {
        "id": 200,
        "name": "beta",
        "full_name": "alice/beta",
        "private": True,
        "default_branch": "main",
        "description": "",
        "html_url": "https://github.com/alice/beta",
        "created_at": "2024-02-01T00:00:00Z",
        "pushed_at": "2024-07-01T00:00:00Z",
    },
]


@pytest.mark.django_db
def test_sync_upserts_repos(github_profile):
    with patch("repositories.services.github_sync.iter_user_repos", return_value=iter(_FAKE_REPOS)):
        count = sync_repositories(github_profile)
    assert count == 2
    assert Repository.objects.filter(github_profile=github_profile).count() == 2
    github_profile.refresh_from_db()
    assert github_profile.last_sync_status == SyncStatus.SUCCESS
    assert github_profile.last_synced_at is not None


@pytest.mark.django_db
def test_sync_is_idempotent(github_profile):
    with patch("repositories.services.github_sync.iter_user_repos", return_value=iter(_FAKE_REPOS)):
        sync_repositories(github_profile)
    with patch("repositories.services.github_sync.iter_user_repos", return_value=iter(_FAKE_REPOS)):
        sync_repositories(github_profile)
    assert Repository.objects.filter(github_profile=github_profile).count() == 2


@pytest.mark.django_db
def test_sync_failure_records_error(github_profile):
    from repositories.services.github_client import GitHubAPIError

    def boom(_token):
        raise GitHubAPIError(401, "Bad credentials")

    with (
        patch("repositories.services.github_sync.iter_user_repos", side_effect=boom),
        pytest.raises(GitHubAPIError),
    ):
        sync_repositories(github_profile)
    github_profile.refresh_from_db()
    assert github_profile.last_sync_status == SyncStatus.FAILURE
    assert "Bad credentials" in github_profile.last_sync_error


# -------- sync endpoint --------

@pytest.mark.django_db
def test_sync_endpoint_without_profile_returns_409(api_client):
    response = api_client.post("/api/v1/repositories/sync")
    assert response.status_code == 409


@pytest.mark.django_db
def test_sync_endpoint_runs_sync(api_client, github_profile):
    with patch("repositories.services.github_sync.iter_user_repos", return_value=iter(_FAKE_REPOS)):
        response = api_client.post("/api/v1/repositories/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["synced"] == 2
    assert body["status"] == SyncStatus.SUCCESS
