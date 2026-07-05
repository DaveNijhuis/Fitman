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
            activity="run",
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
