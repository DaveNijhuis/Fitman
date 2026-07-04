from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _make_session(client: TestClient) -> int:
    resp = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=_auth(client)
    )
    return resp.json()["id"]


def _first_exercise_id(client: TestClient) -> int:
    resp = client.get("/api/exercises?session=Push+A", headers=_auth(client))
    return resp.json()[0]["id"]


# ── Failing tests (red) — validation does not exist yet ──────────────────────


def test_log_rejects_negative_weight(client: TestClient):
    session_id = _make_session(client)
    exercise_id = _first_exercise_id(client)
    resp = client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": -10.0,
            "reps": 8,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 422


def test_log_rejects_zero_reps(client: TestClient):
    session_id = _make_session(client)
    exercise_id = _first_exercise_id(client)
    resp = client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": 30.0,
            "reps": 0,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 422


def test_log_rejects_negative_reps(client: TestClient):
    session_id = _make_session(client)
    exercise_id = _first_exercise_id(client)
    resp = client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": 30.0,
            "reps": -3,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 422


# ── Passing tests (green) — valid edge cases must still work ─────────────────


def test_log_allows_zero_weight_for_bodyweight(client: TestClient):
    session_id = _make_session(client)
    exercises = client.get(
        "/api/exercises?session=Push+A", headers=_auth(client)
    ).json()
    bodyweight_ex = next(e for e in exercises if e["type"] == "bodyweight")
    resp = client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": bodyweight_ex["id"],
            "weight": 0.0,
            "reps": 10,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 201


def test_log_valid_weighted_set(client: TestClient):
    session_id = _make_session(client)
    exercise_id = _first_exercise_id(client)
    resp = client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": 30.0,
            "reps": 8,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["weight"] == 30.0
    assert data["reps"] == 8


# ── POST edge cases ───────────────────────────────────────────────────────────


def test_log_rejects_nonexistent_exercise(client: TestClient):
    session_id = _make_session(client)
    resp = client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": 999999,
            "weight": 30.0,
            "reps": 8,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 404


def test_log_rejects_nonexistent_session(client: TestClient):
    exercise_id = _first_exercise_id(client)
    resp = client.post(
        "/api/logs",
        json={
            "session_id": 999999,
            "exercise_id": exercise_id,
            "weight": 30.0,
            "reps": 8,
        },
        headers=_auth(client),
    )
    assert resp.status_code == 404


# ── GET /logs/last/{exercise_id} ──────────────────────────────────────────────


def test_get_last_log_returns_most_recent(client: TestClient):
    exercise_id = _first_exercise_id(client)
    session_id = _make_session(client)
    client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": 55.0,
            "reps": 8,
        },
        headers=_auth(client),
    )
    resp = client.get(f"/api/logs/last/{exercise_id}", headers=_auth(client))
    assert resp.status_code == 200
    data = resp.json()
    assert data is not None
    assert data["exercise_id"] == exercise_id
    assert data["weight"] == 55.0


def test_get_last_log_returns_null_when_no_logs(client: TestClient):
    exercises = client.get(
        "/api/exercises?session=Legs+A", headers=_auth(client)
    ).json()
    untouched_id = exercises[-1]["id"]
    resp = client.get(f"/api/logs/last/{untouched_id}", headers=_auth(client))
    assert resp.status_code == 200
    assert resp.json() is None


# ── GET /logs ─────────────────────────────────────────────────────────────────


def test_get_logs_for_exercise(client: TestClient):
    exercise_id = _first_exercise_id(client)
    session_id = _make_session(client)
    client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": 40.0,
            "reps": 10,
        },
        headers=_auth(client),
    )
    resp = client.get(f"/api/logs?exercise_id={exercise_id}", headers=_auth(client))
    assert resp.status_code == 200
    logs = resp.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert all(log["exercise_id"] == exercise_id for log in logs)
