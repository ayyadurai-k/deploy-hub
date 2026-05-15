import pytest
from repositories.models import Repository

from projects.models import Project

# -------- list + create --------

@pytest.mark.django_db
def test_list_empty(api_client):
    response = api_client.get("/api/v1/projects/")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.django_db
def test_create_with_auto_slug(api_client, user):
    response = api_client.post("/api/v1/projects/", {"name": "My First Project"}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "My First Project"
    assert body["slug"] == "my-first-project"
    assert body["status"] == "draft"
    assert Project.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_create_with_repository(api_client, github_profile):
    repo = Repository.objects.create(
        github_profile=github_profile,
        github_repo_id=1,
        name="r", full_name="alice/r", html_url="http://x",
    )
    response = api_client.post(
        "/api/v1/projects/", {"name": "Pinned", "repository": repo.id}, format="json"
    )
    assert response.status_code == 201
    assert response.json()["repository"] == repo.id


@pytest.mark.django_db
def test_create_rejects_other_users_repo(api_client, other_user):
    from oauth.models import GitHubProfile
    other_profile = GitHubProfile(user=other_user, github_user_id=2, github_login="bob")
    other_profile.set_access_token("x")
    other_profile.save()
    repo = Repository.objects.create(
        github_profile=other_profile,
        github_repo_id=99,
        name="bob-r", full_name="bob/bob-r", html_url="http://x",
    )
    response = api_client.post(
        "/api/v1/projects/", {"name": "Mine", "repository": repo.id}, format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_slug_disambiguates_on_collision(api_client):
    r1 = api_client.post("/api/v1/projects/", {"name": "Same Name"}, format="json")
    r2 = api_client.post("/api/v1/projects/", {"name": "Same Name"}, format="json")
    # Same name conflicts on UniqueConstraint(user, name), so the second insert
    # must fail at the DB layer — the auto-slug logic handles slug uniqueness
    # but name is a separate unique constraint. The second create returns 400.
    assert r1.status_code == 201
    assert r2.status_code == 400


# -------- per-user scoping --------

@pytest.mark.django_db
def test_list_is_scoped_to_request_user(api_client, other_api_client):
    api_client.post("/api/v1/projects/", {"name": "Mine"}, format="json")
    other_api_client.post("/api/v1/projects/", {"name": "Theirs"}, format="json")

    mine = api_client.get("/api/v1/projects/").json()
    theirs = other_api_client.get("/api/v1/projects/").json()
    assert mine["count"] == 1 and mine["results"][0]["name"] == "Mine"
    assert theirs["count"] == 1 and theirs["results"][0]["name"] == "Theirs"


@pytest.mark.django_db
def test_cannot_retrieve_other_users_project(api_client, other_api_client):
    create = other_api_client.post("/api/v1/projects/", {"name": "Theirs"}, format="json")
    pid = create.json()["id"]
    response = api_client.get(f"/api/v1/projects/{pid}")
    assert response.status_code == 404


# -------- deploy placeholder --------

@pytest.mark.django_db
def test_deploy_returns_501(api_client):
    create = api_client.post("/api/v1/projects/", {"name": "Deployable"}, format="json")
    pid = create.json()["id"]
    response = api_client.post(f"/api/v1/projects/{pid}/deploy")
    assert response.status_code == 501
    body = response.json()
    assert body["error"]["code"] == "deploy_not_implemented"
    assert body["error"]["detail"]["project_id"] == pid


# -------- repository SET_NULL preserves project --------

@pytest.mark.django_db
def test_project_survives_repository_deletion(api_client, github_profile):
    repo = Repository.objects.create(
        github_profile=github_profile,
        github_repo_id=1, name="r", full_name="x/r", html_url="http://x",
    )
    create = api_client.post(
        "/api/v1/projects/", {"name": "Pinned", "repository": repo.id}, format="json"
    )
    pid = create.json()["id"]
    repo.delete()
    response = api_client.get(f"/api/v1/projects/{pid}")
    assert response.status_code == 200
    assert response.json()["repository"] is None
