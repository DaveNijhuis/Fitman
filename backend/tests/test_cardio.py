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
    data = resp.json()
    assert "items" in data
    for entry in data["items"]:
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
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["items"], list)


# ── Pagination (#227) ─────────────────────────────────────────────────────────


def test_cardio_list_default_page_is_1(client: TestClient):
    """Default page / page_size are returned in the envelope."""
    resp = client.get("/api/cardio", headers=_auth(client))
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 50


def test_cardio_list_pagination_slices_correctly(client: TestClient):
    """page_size=1 must return exactly 1 item; total reflects all rows."""
    _post_run(client)
    resp = client.get("/api/cardio?page=1&page_size=1", headers=_auth(client))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] >= 1


def test_cardio_list_page_size_capped_at_200(client: TestClient):
    """page_size values above 200 must be rejected with 422."""
    resp = client.get("/api/cardio?page_size=999", headers=_auth(client))
    assert resp.status_code == 422


def test_cardio_list_page_zero_returns_422(client: TestClient):
    """page=0 is invalid — must return 422."""
    resp = client.get("/api/cardio?page=0", headers=_auth(client))
    assert resp.status_code == 422


def test_cardio_list_beyond_last_page_returns_empty_items(client: TestClient):
    """Page past the end returns items=[] with the real total."""
    resp = client.get("/api/cardio?page=9999&page_size=50", headers=_auth(client))
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] >= 0


def test_cardio_delete_removes_entry(client: TestClient):
    create = _post_run(client)
    entry_id = create.json()["id"]
    resp = client.delete(f"/api/cardio/{entry_id}", headers=_auth(client))
    assert resp.status_code == 204


def test_cardio_list_activities(client: TestClient):
    resp = client.get("/api/cardio/activities", headers=_auth(client))
    assert resp.status_code == 200
    assert "Run" in resp.json()
