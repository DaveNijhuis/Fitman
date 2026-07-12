"""Data isolation tests — each user must only see their own data.

These tests are RED until user_id is added to WorkoutSession, CardioEntry,
and BodyMeasurement and all routers filter by current_user.id.
"""

from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.user import User


def _create_user_b() -> None:
    db = SessionLocal()
    if not db.query(User).filter(User.username == "userb").first():
        db.add(
            User(
                username="userb",
                hashed_password=bcrypt.hashpw(
                    b"passwordB1", bcrypt.gensalt(rounds=4)
                ).decode(),
                is_active=True,
                is_admin=False,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
    db.close()


def _token(client: TestClient, username: str, password: str) -> str:
    return client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]


def _auth_a(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client, 'testuser', 'testpass')}"}


def _auth_b(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client, 'userb', 'passwordB1')}"}


# ── Workout session isolation ─────────────────────────────────────────────────


def test_user_b_cannot_see_user_a_sessions(client: TestClient):
    """User A creates and ends a session; User B must not see it in their list."""
    _create_user_b()

    session = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=_auth_a(client)
    ).json()
    client.patch(f"/api/sessions/{session['id']}/end", headers=_auth_a(client))

    ids = [s["id"] for s in client.get("/api/sessions", headers=_auth_b(client)).json()]
    assert session["id"] not in ids


# ── Cardio isolation ──────────────────────────────────────────────────────────


def test_user_b_cannot_see_user_a_cardio(client: TestClient):
    """User A logs a cardio entry; User B must not see it in their list."""
    _create_user_b()

    entry = client.post(
        "/api/cardio",
        json={"activity": "Run", "distance_m": 5000.0},
        headers=_auth_a(client),
    ).json()

    ids = [e["id"] for e in client.get("/api/cardio", headers=_auth_b(client)).json()]
    assert entry["id"] not in ids


# ── Measurement isolation ─────────────────────────────────────────────────────


def test_user_b_cannot_see_user_a_measurements(client: TestClient):
    """User A logs a measurement; User B must not see it in their list."""
    _create_user_b()

    m = client.post(
        "/api/measurements",
        json={"weight_kg": 85.0},
        headers=_auth_a(client),
    ).json()

    ids = [
        e["id"] for e in client.get("/api/measurements", headers=_auth_b(client)).json()
    ]
    assert m["id"] not in ids


# ── Log isolation (exercise_id filter) ───────────────────────────────────────


def test_user_b_cannot_see_user_a_logs_via_exercise_filter(client: TestClient):
    """User A logs a set; User B querying the same exercise_id must get 0 results.

    GET /api/logs joins through WorkoutSession.user_id — this test makes
    that implicit isolation guarantee explicit and regression-proof.
    """
    _create_user_b()

    # User A: start a session, log one set for exercise 1
    session = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=_auth_a(client)
    ).json()
    client.post(
        "/api/logs",
        json={
            "exercise_id": 1,
            "session_id": session["id"],
            "weight": 100.0,
            "reps": 5,
        },
        headers=_auth_a(client),
    )

    # User B: query the same exercise — must see nothing
    resp = client.get("/api/logs", params={"exercise_id": 1}, headers=_auth_b(client))
    assert resp.status_code == 200
    assert resp.json() == []
