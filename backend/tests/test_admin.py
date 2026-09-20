from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.user import User


def _admin_headers(client: TestClient) -> dict:
    token = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _make_user(
    username: str, password: str = "pass1234", is_admin: bool = False
) -> int:
    db = SessionLocal()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    user = User(
        username=username,
        hashed_password=hashed,
        is_active=True,
        is_admin=is_admin,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


def _nonadmin_headers(client: TestClient) -> dict:
    db = SessionLocal()
    exists = db.query(User).filter(User.username == "nonadmin_user").first()
    db.close()
    if not exists:
        _make_user("nonadmin_user")
    token = client.post(
        "/api/auth/login", json={"username": "nonadmin_user", "password": "pass1234"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── GET /api/admin/users ──────────────────────────────────────────────────────


def test_list_users_requires_auth(client: TestClient):
    assert client.get("/api/admin/users").status_code == 401


def test_list_users_requires_admin(client: TestClient):
    assert (
        client.get("/api/admin/users", headers=_nonadmin_headers(client)).status_code
        == 403
    )


def test_list_users_returns_all_users(client: TestClient):
    resp = client.get("/api/admin/users", headers=_admin_headers(client))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    usernames = [u["username"] for u in data]
    assert "testuser" in usernames


def test_list_users_returns_correct_fields(client: TestClient):
    resp = client.get("/api/admin/users", headers=_admin_headers(client))
    user = next(u for u in resp.json() if u["username"] == "testuser")
    for field in (
        "id",
        "username",
        "email",
        "display_name",
        "is_active",
        "is_admin",
        "created_at",
    ):
        assert field in user


# ── POST /api/admin/users ─────────────────────────────────────────────────────


def test_create_user_requires_auth(client: TestClient):
    assert (
        client.post(
            "/api/admin/users", json={"username": "x", "password": "pass1234"}
        ).status_code
        == 401
    )


def test_create_user_requires_admin(client: TestClient):
    assert (
        client.post(
            "/api/admin/users",
            json={"username": "newone", "password": "pass1234"},
            headers=_nonadmin_headers(client),
        ).status_code
        == 403
    )


def test_create_user_success(client: TestClient):
    resp = client.post(
        "/api/admin/users",
        json={"username": "invited_user", "password": "temppass1"},
        headers=_admin_headers(client),
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "invited_user"
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "invited_user", "password": "temppass1"},
        ).status_code
        == 200
    )


def test_create_user_duplicate_username_returns_409(client: TestClient):
    client.post(
        "/api/admin/users",
        json={"username": "dup_user", "password": "pass1234"},
        headers=_admin_headers(client),
    )
    resp = client.post(
        "/api/admin/users",
        json={"username": "dup_user", "password": "pass1234"},
        headers=_admin_headers(client),
    )
    assert resp.status_code == 409


def test_create_user_rejects_short_password(client: TestClient):
    resp = client.post(
        "/api/admin/users",
        json={"username": "shortpw_user", "password": "short"},
        headers=_admin_headers(client),
    )
    assert resp.status_code == 422


# ── PATCH /api/admin/users/{id} ───────────────────────────────────────────────


def test_disable_user_requires_admin(client: TestClient):
    user_id = _make_user("disable_target")
    assert (
        client.patch(
            f"/api/admin/users/{user_id}",
            json={"is_active": False},
            headers=_nonadmin_headers(client),
        ).status_code
        == 403
    )


def test_disable_user_prevents_login(client: TestClient):
    user_id = _make_user("to_be_disabled", "pass1234")
    client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": False},
        headers=_admin_headers(client),
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "to_be_disabled", "password": "pass1234"},
        ).status_code
        == 403
    )


def test_enable_user_restores_login(client: TestClient):
    user_id = _make_user("to_be_reenabled", "pass1234")
    client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": False},
        headers=_admin_headers(client),
    )
    client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": True},
        headers=_admin_headers(client),
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "to_be_reenabled", "password": "pass1234"},
        ).status_code
        == 200
    )


def test_admin_cannot_disable_self(client: TestClient):
    db = SessionLocal()
    testuser = db.query(User).filter(User.username == "testuser").first()
    assert testuser is not None
    user_id = testuser.id
    db.close()
    resp = client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": False},
        headers=_admin_headers(client),
    )
    assert resp.status_code == 400


# ── DELETE /api/admin/users/{id} ─────────────────────────────────────────────


def test_delete_user_requires_admin(client: TestClient):
    user_id = _make_user("delete_target_auth")
    assert (
        client.delete(
            f"/api/admin/users/{user_id}", headers=_nonadmin_headers(client)
        ).status_code
        == 403
    )


def test_delete_user_success(client: TestClient):
    user_id = _make_user("to_be_deleted", "pass1234")
    resp = client.delete(f"/api/admin/users/{user_id}", headers=_admin_headers(client))
    assert resp.status_code == 204
    usernames = [
        u["username"]
        for u in client.get("/api/admin/users", headers=_admin_headers(client)).json()
    ]
    assert "to_be_deleted" not in usernames


def test_delete_user_removes_their_data(client: TestClient):
    from datetime import datetime
    from datetime import timezone as tz

    from models.workout import WorkoutSession

    user_id = _make_user("data_owner", "pass1234")
    db = SessionLocal()
    db.add(
        WorkoutSession(
            user_id=user_id,
            session="Push A",
            started_at=datetime.now(tz.utc),
        )
    )
    db.commit()
    db.close()

    client.delete(f"/api/admin/users/{user_id}", headers=_admin_headers(client))

    db = SessionLocal()
    remaining = (
        db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).count()
    )
    db.close()
    assert remaining == 0


def test_admin_cannot_delete_self(client: TestClient):
    db = SessionLocal()
    testuser = db.query(User).filter(User.username == "testuser").first()
    assert testuser is not None
    user_id = testuser.id
    db.close()
    resp = client.delete(f"/api/admin/users/{user_id}", headers=_admin_headers(client))
    assert resp.status_code == 400


def test_patch_nonexistent_user_returns_404(client: TestClient):
    resp = client.patch(
        "/api/admin/users/999999",
        json={"is_active": False},
        headers=_admin_headers(client),
    )
    assert resp.status_code == 404


def test_delete_nonexistent_user_returns_404(client: TestClient):
    resp = client.delete(
        "/api/admin/users/999999",
        headers=_admin_headers(client),
    )
    assert resp.status_code == 404
