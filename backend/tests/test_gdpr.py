from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.cardio import CardioEntry
from models.measurement import BodyMeasurement
from models.user import User
from models.workout import Log, WorkoutSession


def _make_user(username: str, password: str = "pass1234") -> int:
    db = SessionLocal()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    user = User(
        username=username,
        hashed_password=hashed,
        is_active=True,
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


def _login(client: TestClient, username: str, password: str = "pass1234") -> dict:
    token = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _seed_data(user_id: int) -> None:
    db = SessionLocal()
    session = WorkoutSession(
        user_id=user_id,
        session="Push A",
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    db.add(
        Log(
            session_id=session.id,
            exercise_id=1,
            weight=80.0,
            reps=8,
            logged_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        CardioEntry(
            user_id=user_id,
            activity="Run",
            duration_s=1800,
            logged_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        BodyMeasurement(
            user_id=user_id,
            weight_kg=80.0,
            recorded_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()


# ── DELETE /api/gdpr/erase ────────────────────────────────────────────────────


def test_erase_requires_auth(client: TestClient):
    assert client.delete("/api/gdpr/erase").status_code == 401


def test_erase_returns_204(client: TestClient):
    _make_user("erase_user_204")
    resp = client.delete("/api/gdpr/erase", headers=_login(client, "erase_user_204"))
    assert resp.status_code == 204


def test_erase_deletes_user_account(client: TestClient):
    _make_user("erase_user_login")
    client.delete("/api/gdpr/erase", headers=_login(client, "erase_user_login"))
    assert (
        client.post(
            "/api/auth/login",
            json={"username": "erase_user_login", "password": "pass1234"},
        ).status_code
        == 401
    )


def test_erase_deletes_workout_data(client: TestClient):
    user_id = _make_user("erase_user_workout")
    _seed_data(user_id)
    client.delete("/api/gdpr/erase", headers=_login(client, "erase_user_workout"))
    db = SessionLocal()
    sessions = (
        db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).count()
    )
    db.close()
    assert sessions == 0


def test_erase_deletes_cardio_data(client: TestClient):
    user_id = _make_user("erase_user_cardio")
    _seed_data(user_id)
    client.delete("/api/gdpr/erase", headers=_login(client, "erase_user_cardio"))
    db = SessionLocal()
    entries = db.query(CardioEntry).filter(CardioEntry.user_id == user_id).count()
    db.close()
    assert entries == 0


def test_erase_deletes_measurement_data(client: TestClient):
    user_id = _make_user("erase_user_measurements")
    _seed_data(user_id)
    client.delete("/api/gdpr/erase", headers=_login(client, "erase_user_measurements"))
    db = SessionLocal()
    measurements = (
        db.query(BodyMeasurement).filter(BodyMeasurement.user_id == user_id).count()
    )
    db.close()
    assert measurements == 0


# ── GET /api/gdpr/export ──────────────────────────────────────────────────────


def test_export_requires_auth(client: TestClient):
    assert client.get("/api/gdpr/export").status_code == 401


def test_export_returns_200(client: TestClient):
    assert (
        client.get(
            "/api/gdpr/export", headers=_login(client, "testuser", "testpass")
        ).status_code
        == 200
    )


def test_export_has_correct_structure(client: TestClient):
    data = client.get(
        "/api/gdpr/export", headers=_login(client, "testuser", "testpass")
    ).json()
    for key in (
        "exported_at",
        "user",
        "workout_sessions",
        "logs",
        "cardio",
        "body_measurements",
    ):
        assert key in data


def test_export_excludes_password_hash(client: TestClient):
    data = client.get(
        "/api/gdpr/export", headers=_login(client, "testuser", "testpass")
    ).json()
    assert "hashed_password" not in data["user"]


def test_export_includes_username(client: TestClient):
    data = client.get(
        "/api/gdpr/export", headers=_login(client, "testuser", "testpass")
    ).json()
    assert data["user"]["username"] == "testuser"


def test_export_sets_content_disposition(client: TestClient):
    resp = client.get(
        "/api/gdpr/export", headers=_login(client, "testuser", "testpass")
    )
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "fitman-export.json" in resp.headers.get("content-disposition", "")


def test_export_includes_workout_sessions(client: TestClient):
    _make_user("export_data_user")
    headers = _login(client, "export_data_user")
    session = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=headers
    ).json()
    client.patch(f"/api/sessions/{session['id']}/end", headers=headers)
    data = client.get("/api/gdpr/export", headers=headers).json()
    assert isinstance(data["workout_sessions"], list)
    assert any(s["id"] == session["id"] for s in data["workout_sessions"])


# ── Fixture data integrity (#183) ─────────────────────────────────────────────


def test_seed_data_cardio_activity_is_valid(client: TestClient):
    """_seed_data must seed a valid title-case activity, not a raw lowercase string.

    CardioEntry is inserted directly into the DB so the API validation in
    POST /api/cardio is bypassed. If the activity value is wrong it silently
    persists and pollutes GDPR exports with invalid data.
    """
    from routers.cardio import ACTIVITIES

    user_id = _make_user("seed_activity_check")
    _seed_data(user_id)

    db = SessionLocal()
    entry = db.query(CardioEntry).filter(CardioEntry.user_id == user_id).first()
    db.close()

    assert entry is not None
    assert entry.activity in ACTIVITIES, (
        f"Seeded activity {entry.activity!r} is not a valid value; expected one of {ACTIVITIES}"
    )
