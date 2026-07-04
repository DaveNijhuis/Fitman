from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


# ── Sessions list ─────────────────────────────────────────────────────────────


def test_list_sessions_returns_known_names(client: TestClient):
    resp = client.get("/api/exercises/sessions", headers=_auth(client))
    assert resp.status_code == 200
    sessions = resp.json()
    assert "Push A" in sessions
    assert "Pull A" in sessions
    assert "Legs A" in sessions


# ── Exercise list ─────────────────────────────────────────────────────────────


def test_list_exercises_unknown_session_returns_400(client: TestClient):
    resp = client.get("/api/exercises?session=Chest+Day", headers=_auth(client))
    assert resp.status_code == 400


def test_list_exercises_search_filter(client: TestClient):
    resp = client.get("/api/exercises?search=bench", headers=_auth(client))
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) > 0
    assert all("bench" in ex["name"].lower() for ex in results)


def test_list_exercises_search_returns_empty_for_no_match(client: TestClient):
    resp = client.get("/api/exercises?search=xyznonexistent", headers=_auth(client))
    assert resp.status_code == 200
    assert resp.json() == []


# ── Exercise by ID ────────────────────────────────────────────────────────────


def test_get_exercise_by_id(client: TestClient):
    headers = _auth(client)
    exercise_id = client.get("/api/exercises?session=Push+A", headers=headers).json()[
        0
    ]["id"]
    resp = client.get(f"/api/exercises/{exercise_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == exercise_id
    assert "name" in data
    assert "session" in data


def test_get_exercise_by_id_not_found(client: TestClient):
    resp = client.get("/api/exercises/999999", headers=_auth(client))
    assert resp.status_code == 404
