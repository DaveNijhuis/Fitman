from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _post_run(client: TestClient):
    resp = client.post(
        "/api/cardio",
        json={"activity": "Run", "distance_m": 5000.0, "duration_s": 1800},
        headers=_auth(client),
    )
    return resp


# ── Schema contract (RED until CardioEntry replaces CardioSession+CardioLog) ──


def test_cardio_log_response_has_no_session_id(client: TestClient):
    """Response must not expose the internal session_id — entries are flat."""
    resp = _post_run(client)
    assert resp.status_code == 201
    assert "session_id" not in resp.json()


def test_cardio_list_has_no_session_id(client: TestClient):
    """List response must not include session_id on any entry."""
    _post_run(client)
    resp = client.get("/api/cardio", headers=_auth(client))
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) > 0
    for entry in entries:
        assert "session_id" not in entry


# ── Endpoint contract (should pass before and after refactor) ─────────────────


def test_cardio_log_valid_entry(client: TestClient):
    resp = _post_run(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["activity"] == "Run"
    assert data["distance_m"] == 5000.0
    assert data["duration_s"] == 1800


def test_cardio_rejects_unknown_activity(client: TestClient):
    resp = client.post(
        "/api/cardio",
        json={"activity": "Skydiving"},
        headers=_auth(client),
    )
    assert resp.status_code == 400


def test_cardio_list_returns_entries(client: TestClient):
    resp = client.get("/api/cardio", headers=_auth(client))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_cardio_delete_removes_entry(client: TestClient):
    create = _post_run(client)
    entry_id = create.json()["id"]
    resp = client.delete(f"/api/cardio/{entry_id}", headers=_auth(client))
    assert resp.status_code == 204


def test_cardio_list_activities(client: TestClient):
    resp = client.get("/api/cardio/activities", headers=_auth(client))
    assert resp.status_code == 200
    assert "Run" in resp.json()
