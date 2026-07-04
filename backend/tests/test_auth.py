import bcrypt
from fastapi.testclient import TestClient

from routers.auth import _verify_password

# ── Unit tests ────────────────────────────────────────────────────────────────

def test_verify_password_correct():
    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    assert _verify_password("secret", hashed) is True


def test_verify_password_wrong():
    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    assert _verify_password("wrong", hashed) is False


# ── Setup endpoint ────────────────────────────────────────────────────────────

def test_setup_not_required_when_user_exists(client: TestClient):
    resp = client.get("/api/auth/setup-required")
    assert resp.status_code == 200
    assert resp.json()["required"] is False


def test_register_fails_when_user_exists(client: TestClient):
    resp = client.post("/api/auth/register", json={"username": "newuser", "password": "pass123"})
    assert resp.status_code == 409


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_success(client: TestClient):
    resp = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient):
    resp = client.post("/api/auth/login", json={"username": "testuser", "password": "wrong"})
    assert resp.status_code == 401


def test_login_wrong_username(client: TestClient):
    resp = client.post("/api/auth/login", json={"username": "wrong", "password": "testpass"})
    assert resp.status_code == 401


# ── Protected endpoints ───────────────────────────────────────────────────────

def test_protected_endpoint_without_token(client: TestClient):
    resp = client.get("/api/exercises")
    assert resp.status_code == 401


def test_protected_endpoint_with_valid_token(client: TestClient):
    login = client.post("/api/auth/login", json={"username": "testuser", "password": "testpass"})
    token = login.json()["access_token"]
    resp = client.get("/api/exercises", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
