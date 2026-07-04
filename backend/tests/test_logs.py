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
