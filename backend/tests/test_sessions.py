from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _start(client: TestClient, name: str = "Push A") -> dict:
    return client.post(
        "/api/sessions", json={"session": name}, headers=_auth(client)
    ).json()


def _first_exercise_id(client: TestClient) -> int:
    return client.get("/api/exercises?session=Push+A", headers=_auth(client)).json()[0][
        "id"
    ]


def _log_set(client: TestClient, session_id: int, exercise_id: int) -> None:
    client.post(
        "/api/logs",
        json={
            "session_id": session_id,
            "exercise_id": exercise_id,
            "weight": 40.0,
            "reps": 8,
        },
        headers=_auth(client),
    )


# ── Start session ─────────────────────────────────────────────────────────────


def test_start_session_returns_201(client: TestClient):
    resp = client.post(
        "/api/sessions", json={"session": "Push A"}, headers=_auth(client)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["session"] == "Push A"
    assert data["ended_at"] is None
    assert "started_at" in data
    assert "id" in data


def test_start_session_rejects_unknown_name(client: TestClient):
    resp = client.post(
        "/api/sessions", json={"session": "Chest Day"}, headers=_auth(client)
    )
    assert resp.status_code == 400


# ── End session ───────────────────────────────────────────────────────────────


def test_end_session_sets_ended_at(client: TestClient):
    session = _start(client)
    resp = client.patch(f"/api/sessions/{session['id']}/end", headers=_auth(client))
    assert resp.status_code == 200
    assert resp.json()["ended_at"] is not None


def test_end_session_already_ended_returns_400(client: TestClient):
    session = _start(client)
    client.patch(f"/api/sessions/{session['id']}/end", headers=_auth(client))
    resp = client.patch(f"/api/sessions/{session['id']}/end", headers=_auth(client))
    assert resp.status_code == 400


def test_end_nonexistent_session_returns_404(client: TestClient):
    resp = client.patch("/api/sessions/999999/end", headers=_auth(client))
    assert resp.status_code == 404


# ── List sessions ─────────────────────────────────────────────────────────────


def test_list_sessions_returns_only_completed(client: TestClient):
    """An in-progress session (no ended_at) must not appear in the list."""
    before = client.get("/api/sessions", headers=_auth(client)).json()
    in_progress = _start(client)

    after = client.get("/api/sessions", headers=_auth(client)).json()
    ids = [s["id"] for s in after]
    assert in_progress["id"] not in ids
    assert len(after) == len(before)


def test_list_sessions_includes_volume_and_set_count(client: TestClient):
    exercise_id = _first_exercise_id(client)
    session = _start(client)
    _log_set(client, session["id"], exercise_id)
    _log_set(client, session["id"], exercise_id)
    client.patch(f"/api/sessions/{session['id']}/end", headers=_auth(client))

    sessions = client.get("/api/sessions", headers=_auth(client)).json()
    match = next(s for s in sessions if s["id"] == session["id"])
    assert match["set_count"] == 2
    assert match["volume_kg"] == 40.0 * 8 * 2


# ── Session logs ──────────────────────────────────────────────────────────────


def test_get_session_logs_returns_entries_with_exercise_name(client: TestClient):
    exercise_id = _first_exercise_id(client)
    session = _start(client)
    _log_set(client, session["id"], exercise_id)
    client.patch(f"/api/sessions/{session['id']}/end", headers=_auth(client))

    resp = client.get(f"/api/sessions/{session['id']}/logs", headers=_auth(client))
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) == 1
    assert logs[0]["exercise_id"] == exercise_id
    assert isinstance(logs[0]["exercise_name"], str)
    assert logs[0]["weight"] == 40.0
    assert logs[0]["reps"] == 8


def test_get_session_logs_nonexistent_session_returns_404(client: TestClient):
    resp = client.get("/api/sessions/999999/logs", headers=_auth(client))
    assert resp.status_code == 404


# ── N+1 regression (#129) ────────────────────────────────────────────────────


def test_list_sessions_single_query(client: TestClient):
    """GET /api/sessions must not fire a query per session (N+1 anti-pattern).

    Seeds 5 completed sessions then counts SELECT statements issued during the
    list request.  The current N+1 implementation fires 1 (sessions fetch) +
    5 (one logs query per session) = 6 queries inside the handler, which exceeds
    the budget of ≤2 (auth + one aggregated join).
    """
    from sqlalchemy import event

    from database import engine

    exercise_id = _first_exercise_id(client)
    headers = _auth(client)

    for _ in range(5):
        s = _start(client)
        _log_set(client, s["id"], exercise_id)
        _log_set(client, s["id"], exercise_id)
        client.patch(f"/api/sessions/{s['id']}/end", headers=headers)

    query_count = 0

    def _count(conn, cursor, statement, parameters, context, executemany):
        nonlocal query_count
        if statement.strip().upper().startswith("SELECT"):
            query_count += 1

    event.listen(engine, "before_cursor_execute", _count)
    try:
        resp = client.get("/api/sessions", headers=headers)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert resp.status_code == 200
    assert query_count <= 2, f"N+1 detected: {query_count} SELECT queries (expected ≤2)"


# ── Full flow ─────────────────────────────────────────────────────────────────


def test_full_workout_session_flow(client: TestClient):
    """Start → log 3 sets → end → verify in list → verify logs."""
    exercise_id = _first_exercise_id(client)
    headers = _auth(client)

    # Start
    session = client.post(
        "/api/sessions", json={"session": "Pull A"}, headers=headers
    ).json()
    assert session["ended_at"] is None

    # Log 3 sets
    for weight in [60.0, 65.0, 70.0]:
        client.post(
            "/api/logs",
            json={
                "session_id": session["id"],
                "exercise_id": exercise_id,
                "weight": weight,
                "reps": 6,
            },
            headers=headers,
        )

    # End
    ended = client.patch(f"/api/sessions/{session['id']}/end", headers=headers).json()
    assert ended["ended_at"] is not None

    # Appears in list with correct aggregates
    sessions = client.get("/api/sessions", headers=headers).json()
    match = next(s for s in sessions if s["id"] == session["id"])
    assert match["set_count"] == 3
    assert match["volume_kg"] == (60.0 + 65.0 + 70.0) * 6

    # Logs endpoint returns all 3 sets
    logs = client.get(f"/api/sessions/{session['id']}/logs", headers=headers).json()
    assert len(logs) == 3
