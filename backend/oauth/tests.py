import pytest

from oauth.services import state as state_svc
from oauth.services.token_crypto import decrypt, encrypt

# -------- token_crypto --------

def test_encrypt_decrypt_roundtrip():
    secret = "ghp_abc123-very-secret-token"
    cipher = encrypt(secret)
    assert cipher != secret
    assert decrypt(cipher) == secret


def test_encrypt_produces_different_ciphertext_each_time():
    plaintext = "same input"
    a = encrypt(plaintext)
    b = encrypt(plaintext)
    assert a != b
    assert decrypt(a) == decrypt(b) == plaintext


def test_decrypt_tampered_ciphertext_raises():
    from cryptography.fernet import InvalidToken
    cipher = encrypt("hello")
    tampered = cipher[:-4] + "AAAA"
    with pytest.raises(InvalidToken):
        decrypt(tampered)


# -------- state service --------

def test_state_roundtrip():
    nonce, env = state_svc.issue_state("github", "login")
    payload = state_svc.verify_state(nonce, env, "github")
    assert payload.provider == "github"
    assert payload.intent == "login"
    assert payload.owner_user_id is None


def test_state_link_carries_owner_id():
    nonce, env = state_svc.issue_state("google", "link", owner_user_id=42)
    payload = state_svc.verify_state(nonce, env, "google")
    assert payload.owner_user_id == 42
    assert payload.intent == "link"


def test_state_tamper_detection():
    nonce, env = state_svc.issue_state("github", "login")
    with pytest.raises(ValueError, match="signature"):
        state_svc.verify_state(nonce, env + "x", "github")


def test_state_provider_mismatch():
    nonce, env = state_svc.issue_state("github", "login")
    with pytest.raises(ValueError, match="provider"):
        state_svc.verify_state(nonce, env, "google")


def test_state_nonce_mismatch():
    _, env = state_svc.issue_state("github", "login")
    with pytest.raises(ValueError, match="nonce"):
        state_svc.verify_state("wrong-nonce", env, "github")


def test_state_missing_inputs():
    with pytest.raises(ValueError, match="missing"):
        state_svc.verify_state("", "envelope", "github")
    with pytest.raises(ValueError, match="missing"):
        state_svc.verify_state("nonce", "", "github")


# -------- OAuth start endpoints (no provider network) --------

@pytest.mark.django_db
def test_get_google_start_redirects_with_state_cookie(unauth_client):
    response = unauth_client.get("/api/v1/oauth/google/start")
    assert response.status_code == 302
    assert "accounts.google.com" in response["Location"]
    assert "oauth_state" in response.cookies


@pytest.mark.django_db
def test_get_github_start_redirects_with_state_cookie(unauth_client):
    response = unauth_client.get("/api/v1/oauth/github/start")
    assert response.status_code == 302
    assert "github.com/login/oauth/authorize" in response["Location"]
    assert "oauth_state" in response.cookies


@pytest.mark.django_db
def test_post_start_requires_auth(unauth_client):
    response = unauth_client.post("/api/v1/oauth/github/start")
    assert response.status_code == 401


@pytest.mark.django_db
def test_post_start_authed_returns_authorize_url(api_client):
    response = api_client.post("/api/v1/oauth/github/start")
    assert response.status_code == 200
    body = response.json()
    assert "authorize_url" in body
    assert "github.com" in body["authorize_url"]


# -------- OAuth callback error paths --------

@pytest.mark.django_db
def test_callback_with_no_state_redirects_to_spa_with_error(unauth_client):
    response = unauth_client.get("/api/v1/oauth/google/callback?code=x&state=y")
    assert response.status_code == 302
    assert "auth/complete" in response["Location"]
    assert "error=" in response["Location"]
