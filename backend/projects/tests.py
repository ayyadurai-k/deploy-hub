import pytest

from projects.models import Project


@pytest.mark.django_db
def test_list_empty(api_client):
    response = api_client.get("/api/v1/projects/")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "next": None, "previous": None, "results": []}


@pytest.mark.django_db
def test_list_requires_auth(unauth_client):
    response = unauth_client.get("/api/v1/projects/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_list_is_scoped_to_request_user(api_client, user, other_user):
    Project.objects.create(user=user, name="Mine", slug="mine")
    Project.objects.create(user=other_user, name="Theirs", slug="theirs")
    body = api_client.get("/api/v1/projects/").json()
    assert body["count"] == 1
    assert body["results"][0]["name"] == "Mine"


@pytest.mark.django_db
def test_list_returns_serialized_fields(api_client, user):
    Project.objects.create(user=user, name="Demo", slug="demo")
    row = api_client.get("/api/v1/projects/").json()["results"][0]
    assert row["name"] == "Demo"
    assert row["slug"] == "demo"
    assert row["status"] == "draft"
    assert row["repository"] is None
