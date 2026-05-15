import pytest


@pytest.mark.django_db
def test_healthz(unauth_client):
    response = unauth_client.get("/api/v1/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz(unauth_client):
    response = unauth_client.get("/api/v1/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


@pytest.mark.django_db
def test_unauthenticated_endpoint_returns_error_envelope(unauth_client):
    response = unauth_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "not_authenticated"
    assert "message" in body["error"]


def test_request_id_middleware_echo(client):
    response = client.get("/api/v1/healthz", HTTP_HOST="localhost", HTTP_X_REQUEST_ID="abc-123")
    assert response.headers["X-Request-ID"] == "abc-123"


def test_request_id_middleware_generates(client):
    response = client.get("/api/v1/healthz", HTTP_HOST="localhost")
    rid = response.headers["X-Request-ID"]
    assert rid
    assert len(rid) >= 16
