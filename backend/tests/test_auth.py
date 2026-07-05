from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.user import User
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
    resp = client.post(
        "/api/auth/register", json={"username": "newuser", "password": "pass1234"}
    )
    assert resp.status_code == 409


# ── Login ─────────────────────────────────────────────────────────────────────


def test_login_success(client: TestClient):
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient):
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_login_wrong_username(client: TestClient):
    resp = client.post(
        "/api/auth/login", json={"username": "wrong", "password": "testpass"}
    )
    assert resp.status_code == 401


# ── Protected endpoints ───────────────────────────────────────────────────────


def test_protected_endpoint_without_token(client: TestClient):
    resp = client.get("/api/exercises")
    assert resp.status_code == 401


def test_protected_endpoint_with_valid_token(client: TestClient):
    login = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    token = login.json()["access_token"]
    resp = client.get("/api/exercises", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


# ── Registration password validation (Issue #123) ─────────────────────────────


def test_register_rejects_empty_password(client: TestClient):
    resp = client.post(
        "/api/auth/register", json={"username": "newuser", "password": ""}
    )
    assert resp.status_code == 422


def test_register_rejects_short_password(client: TestClient):
    """Password under 8 chars must be rejected by Pydantic before the DB is touched."""
    resp = client.post(
        "/api/auth/register", json={"username": "newuser", "password": "abc123"}
    )
    assert resp.status_code == 422


def test_register_rejects_7_char_password(client: TestClient):
    """Boundary: 7 chars must fail — minimum is 8."""
    resp = client.post(
        "/api/auth/register", json={"username": "newuser", "password": "1234567"}
    )
    assert resp.status_code == 422


def test_register_accepts_minimum_length_password(client: TestClient):
    """Boundary: 8-char password must pass Pydantic validation.
    Setup already complete so DB returns 409 — but not 422, proving validation passed."""
    resp = client.post(
        "/api/auth/register", json={"username": "newuser", "password": "12345678"}
    )
    assert resp.status_code == 409


# ── Change password (Issue #106) ──────────────────────────────────────────────


def _make_user(username: str, password: str) -> None:
    db = SessionLocal()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    db.add(
        User(
            username=username,
            hashed_password=hashed,
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()


def _login(client: TestClient, username: str, password: str) -> dict:
    token = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_change_password_requires_auth(client: TestClient):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "testpass", "new_password": "newpass1234"},
    )
    assert resp.status_code == 401


def test_change_password_rejects_wrong_current(client: TestClient):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "wrongpassword", "new_password": "newpass1234"},
        headers=_login(client, "testuser", "testpass"),
    )
    assert resp.status_code == 400


def test_change_password_rejects_short_new_password(client: TestClient):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "testpass", "new_password": "short"},
        headers=_login(client, "testuser", "testpass"),
    )
    assert resp.status_code == 422


def test_change_password_success(client: TestClient):
    _make_user("pw_change_user", "oldpass1234")
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "oldpass1234", "new_password": "newpass5678"},
        headers=_login(client, "pw_change_user", "oldpass1234"),
    )
    assert resp.status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "pw_change_user", "password": "newpass5678"},
        ).status_code
        == 200
    )


def test_change_password_old_password_rejected_after_change(client: TestClient):
    _make_user("pw_old_user", "oldpass1234")
    client.post(
        "/api/auth/change-password",
        json={"current_password": "oldpass1234", "new_password": "newpass5678"},
        headers=_login(client, "pw_old_user", "oldpass1234"),
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "pw_old_user", "password": "oldpass1234"},
        ).status_code
        == 401
    )
