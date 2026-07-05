from datetime import datetime, timezone

from fastapi.testclient import TestClient

from database import SessionLocal
from models.exercise import Exercise
from models.workout import Log, WorkoutSession
from routers.progress import epley_1rm


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _log_and_end(
    client: TestClient, exercise_id: int, weight: float, reps: int
) -> None:
    headers = {"Authorization": f"Bearer {_token(client)}"}
    session = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=headers
    ).json()
    client.post(
        "/api/logs",
        json={
            "session_id": session["id"],
            "exercise_id": exercise_id,
            "weight": weight,
            "reps": reps,
        },
        headers=headers,
    )
    client.patch(f"/api/sessions/{session['id']}/end", headers=headers)


# ── Muscle balance ────────────────────────────────────────────────────────────


def test_balance_returns_list(client: TestClient):
    resp = client.get("/api/progress/balance", headers=_auth(client))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_balance_returns_muscle_groups(client: TestClient):
    headers = _auth(client)

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
        user_id=1,
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
    assert "" not in [row["muscle"] for row in resp.json()]


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
        user_id=1,
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
    assert "" not in [row["muscle"] for row in resp.json()]


# ── Unit tests for epley_1rm ──────────────────────────────────────────────────


def test_epley_1rm_single_rep():
    assert epley_1rm(100.0, 1) == 100.0


def test_epley_1rm_formula():
    assert epley_1rm(100.0, 10) == 100.0 * (1 + 10 / 30)


# ── Strength progression ──────────────────────────────────────────────────────


def test_strength_progression_unknown_exercise_returns_404(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.get("/api/progress/strength?exercise_id=999999", headers=headers)
    assert resp.status_code == 404


def test_strength_progression_returns_correct_structure(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    exercise_id = client.get("/api/exercises?session=Push+A", headers=headers).json()[
        0
    ]["id"]
    _log_and_end(client, exercise_id, 80.0, 5)

    resp = client.get(
        f"/api/progress/strength?exercise_id={exercise_id}", headers=headers
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exercise_id"] == exercise_id
    assert isinstance(data["exercise_name"], str)
    assert isinstance(data["data"], list)
    assert len(data["data"]) > 0
    assert "date" in data["data"][0]
    assert "estimated_1rm" in data["data"][0]


def test_strength_progression_uses_daily_best(client: TestClient):
    """Two sets logged today: the endpoint must reflect the heavier 1RM."""
    headers = {"Authorization": f"Bearer {_token(client)}"}
    exercise_id = client.get("/api/exercises?session=Push+A", headers=headers).json()[
        0
    ]["id"]
    session = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=headers
    ).json()
    for weight in [10.0, 100.0]:
        client.post(
            "/api/logs",
            json={
                "session_id": session["id"],
                "exercise_id": exercise_id,
                "weight": weight,
                "reps": 5,
            },
            headers=headers,
        )
    client.patch(f"/api/sessions/{session['id']}/end", headers=headers)

    resp = client.get(
        f"/api/progress/strength?exercise_id={exercise_id}", headers=headers
    )
    today = datetime.now(timezone.utc).date().isoformat()
    points = {p["date"]: p["estimated_1rm"] for p in resp.json()["data"]}
    assert today in points
    assert points[today] >= round(epley_1rm(100.0, 5), 2)


# ── Volume over time ──────────────────────────────────────────────────────────


def test_volume_over_time_returns_list(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.get("/api/progress/volume", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_volume_over_time_has_correct_structure(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    data = client.get("/api/progress/volume", headers=headers).json()
    if data:
        assert "week" in data[0]
        assert "volume_kg" in data[0]


# ── Consistency heatmap ───────────────────────────────────────────────────────


def test_consistency_returns_17_weeks(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.get("/api/progress/consistency", headers=headers)
    assert resp.status_code == 200
    weeks = resp.json()
    assert len(weeks) == 17
    for week in weeks:
        assert "week" in week
        assert len(week["days"]) == 7


def test_consistency_each_day_has_required_fields(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    weeks = client.get("/api/progress/consistency", headers=headers).json()
    for week in weeks:
        for day in week["days"]:
            assert "date" in day
            assert "trained" in day


# ── Personal records ──────────────────────────────────────────────────────────


def test_prs_returns_list(client: TestClient):
    headers = {"Authorization": f"Bearer {_token(client)}"}
    resp = client.get("/api/progress/prs", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_prs_picks_best_set_per_exercise(client: TestClient):
    """Single-rep set: estimated_1rm must equal the weight exactly."""
    headers = {"Authorization": f"Bearer {_token(client)}"}
    exercise_id = client.get("/api/exercises?session=Push+A", headers=headers).json()[
        0
    ]["id"]
    _log_and_end(client, exercise_id, 100.0, 1)

    prs = client.get("/api/progress/prs", headers=headers).json()
    match = next((pr for pr in prs if pr["exercise_id"] == exercise_id), None)
    assert match is not None
    assert match["estimated_1rm"] >= 100.0
    assert "exercise_name" in match
    assert "date" in match


# ── N+1 regression (#130) ─────────────────────────────────────────────────────


def test_prs_single_query(client: TestClient):
    """GET /api/progress/prs must not fire one query per exercise (N+1).

    The current implementation fetches all exercises then calls _user_logs per
    exercise in a loop.  With 30 exercises in the seed library the handler fires
    31+ SELECT statements.  The fix uses a single joined query, so total SELECT
    count must be ≤3 (auth + one aggregated join).
    """
    from sqlalchemy import event

    from database import engine

    headers = _auth(client)

    # Seed logs across three exercises so N+1 is observable
    exercises = client.get("/api/exercises?session=Push+A", headers=headers).json()
    for ex in exercises[:3]:
        _log_and_end(client, ex["id"], 60.0, 8)

    query_count = 0

    def _count(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if statement.strip().upper().startswith("SELECT"):
            query_count += 1

    event.listen(engine, "before_cursor_execute", _count)
    try:
        resp = client.get("/api/progress/prs", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert resp.status_code == 200
    assert query_count <= 3, f"N+1 detected: {query_count} SELECT queries (expected ≤3)"
