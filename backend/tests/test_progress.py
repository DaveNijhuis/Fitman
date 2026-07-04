from datetime import datetime, timezone

from fastapi.testclient import TestClient

from database import SessionLocal
from models.exercise import Exercise
from models.workout import Log, WorkoutSession


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def test_balance_returns_list(client: TestClient):
    resp = client.get("/api/progress/balance", headers=_auth(client))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_balance_returns_muscle_groups(client: TestClient):
    headers = _auth(client)

    # Get the first Push A exercise (Flat DB Bench Press → Chest, Front Delt, Triceps)
    exercises = client.get("/api/exercises?session=Push+A", headers=headers).json()
    ex = exercises[0]

    session = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=headers
    ).json()
    client.post(
        "/api/logs",
        json={
            "session_id": session["id"],
            "exercise_id": ex["id"],
            "weight": 30.0,
            "reps": 10,
        },
        headers=headers,
    )
    client.patch(f"/api/sessions/{session['id']}/end", headers=headers)

    resp = client.get("/api/progress/balance", headers=headers)
    assert resp.status_code == 200
    muscles = [row["muscle"] for row in resp.json()]
    assert len(muscles) > 0
    assert all(row["percentage"] > 0 for row in resp.json())
    total_pct = sum(row["percentage"] for row in resp.json())
    assert abs(total_pct - 100.0) < 0.2


def test_balance_skips_exercise_with_null_muscles(client: TestClient):
    """Exercise with NULL muscles must not crash the endpoint."""
    headers = _auth(client)

    db = SessionLocal()
    null_ex = Exercise(
        name="Test NULL muscles",
        muscles=None,
        session="Push A",
        position=99,
        type="weight",
        equip="Dumbbell",
    )
    db.add(null_ex)
    db.commit()
    db.refresh(null_ex)

    session_obj = WorkoutSession(
        session="Push A",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    db.add(
        Log(
            session_id=session_obj.id,
            exercise_id=null_ex.id,
            weight=20.0,
            reps=8,
            logged_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()

    resp = client.get("/api/progress/balance", headers=headers)
    assert resp.status_code == 200
    muscles = [row["muscle"] for row in resp.json()]
    assert "" not in muscles


def test_balance_skips_exercise_with_malformed_muscles(client: TestClient):
    """Exercise with muscles like ',,' must not produce empty-string muscle groups."""
    headers = _auth(client)

    db = SessionLocal()
    bad_ex = Exercise(
        name="Test malformed muscles",
        muscles=",,",
        session="Push A",
        position=98,
        type="weight",
        equip="Dumbbell",
    )
    db.add(bad_ex)
    db.commit()
    db.refresh(bad_ex)

    session_obj = WorkoutSession(
        session="Push A",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    db.add(
        Log(
            session_id=session_obj.id,
            exercise_id=bad_ex.id,
            weight=20.0,
            reps=8,
            logged_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()

    resp = client.get("/api/progress/balance", headers=headers)
    assert resp.status_code == 200
    muscles = [row["muscle"] for row in resp.json()]
    assert "" not in muscles
