from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def test_log_basic_measurement(client: TestClient):
    token = _token(client)
    resp = client.post(
        "/api/measurements",
        json={"weight_kg": 80.5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["weight_kg"] == 80.5
    assert data["id"] is not None
    assert data["recorded_at"] is not None


def test_log_full_body_composition(client: TestClient):
    token = _token(client)
    payload = {
        "weight_kg": 80.5,
        "body_fat_pct": 18.2,
        "skeletal_muscle_kg": 38.1,
        "bmr_kcal": 1850.0,
        "ra_z20": 312.5,
        "la_z20": 308.0,
        "rl_z20": 210.0,
        "ll_z20": 208.5,
        "trunk_z20": 42,
        "ra_z100": 290.0,
        "la_z100": 287.0,
        "rl_z100": 195.0,
        "ll_z100": 193.0,
        "trunk_z100": 38,
    }
    resp = client.post(
        "/api/measurements",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["body_fat_pct"] == 18.2
    assert data["ra_z20"] == 312.5
    assert data["trunk_z100"] == 38


def test_list_measurements(client: TestClient):
    token = _token(client)
    resp = client.get("/api/measurements", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["items"], list)


# ── Pagination (#227) ─────────────────────────────────────────────────────────


def _post_weight(client: TestClient, weight: float) -> None:
    client.post(
        "/api/measurements",
        json={"weight_kg": weight},
        headers={"Authorization": f"Bearer {_token(client)}"},
    )


def test_list_measurements_default_page_is_1(client: TestClient):
    """Default page / page_size are returned in the envelope."""
    resp = client.get(
        "/api/measurements",
        headers={"Authorization": f"Bearer {_token(client)}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 50


def test_list_measurements_pagination_slices_correctly(client: TestClient):
    """page_size=1 must return exactly 1 item; total reflects all rows."""
    _post_weight(client, 73.0)
    resp = client.get(
        "/api/measurements?page=1&page_size=1",
        headers={"Authorization": f"Bearer {_token(client)}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["total"] >= 1


def test_list_measurements_page_size_capped_at_200(client: TestClient):
    """page_size values above 200 must be rejected with 422."""
    resp = client.get(
        "/api/measurements?page_size=999",
        headers={"Authorization": f"Bearer {_token(client)}"},
    )
    assert resp.status_code == 422


def test_list_measurements_page_zero_returns_422(client: TestClient):
    """page=0 is invalid (pages start at 1) — must return 422."""
    resp = client.get(
        "/api/measurements?page=0",
        headers={"Authorization": f"Bearer {_token(client)}"},
    )
    assert resp.status_code == 422


def test_list_measurements_beyond_last_page_returns_empty_items(client: TestClient):
    """Requesting a page past the end returns items=[] with the real total."""
    resp = client.get(
        "/api/measurements?page=9999&page_size=50",
        headers={"Authorization": f"Bearer {_token(client)}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] >= 0


def test_delete_measurement(client: TestClient):
    token = _token(client)
    created = client.post(
        "/api/measurements",
        json={"weight_kg": 79.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    mid = created.json()["id"]
    resp = client.delete(
        f"/api/measurements/{mid}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204


def test_delete_nonexistent_measurement(client: TestClient):
    token = _token(client)
    resp = client.delete(
        "/api/measurements/999999", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_measurement_without_token():
    from main import app

    c = TestClient(app)
    assert c.get("/api/measurements").status_code == 401


# ── BIA formula application (Issue #127) ─────────────────────────────────────


def test_bia_formulae_applied_when_all_inputs_provided(client: TestClient):
    """Full BIA payload with user_age + user_sex must trigger calculate_all
    and populate derived fields (bmi, fat_mass_kg, lean_mass_kg, etc.)."""
    token = _token(client)
    payload = {
        "weight_kg": 80.0,
        "height_cm": 180.0,
        "body_fat_pct": 18.2,
        "user_age": 30,
        "user_sex": 1,
        "ra_z20": 312.5,
        "la_z20": 308.0,
        "rl_z20": 210.0,
        "ll_z20": 208.5,
        "trunk_z20": 42.0,
        "ra_z100": 290.0,
        "la_z100": 287.0,
        "rl_z100": 195.0,
        "ll_z100": 193.0,
        "trunk_z100": 38.0,
    }
    resp = client.post(
        "/api/measurements",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bmi"] is not None
    assert data["fat_mass_kg"] is not None
    assert data["lean_mass_kg"] is not None
    assert data["bmr_kcal"] is not None
    expected_bmi = round(80.0 / (1.80**2), 1)
    assert abs(data["bmi"] - expected_bmi) < 0.5


def test_bia_formulae_skipped_when_inputs_incomplete(client: TestClient):
    """Payload missing impedance data must leave derived fields as None."""
    token = _token(client)
    resp = client.post(
        "/api/measurements",
        json={"weight_kg": 80.0, "body_fat_pct": 18.2, "user_age": 30, "user_sex": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bmi"] is None
    assert data["fat_mass_kg"] is None


def test_bia_formulae_run_when_body_fat_pct_is_zero(client: TestClient):
    """body_fat_pct=0.0 is falsy but present — formulas must still run.

    all(required) treats 0.0 as absent and skips all formulae, so bmi is
    never computed even though height, weight, age, and all impedance values
    are provided.  The correct guard is all(x is not None for x in required).
    """
    token = _token(client)
    payload = {
        "weight_kg": 80.0,
        "height_cm": 175.0,
        "body_fat_pct": 0.0,
        "user_age": 35,
        "user_sex": 1,
        "ra_z20": 312.5,
        "la_z20": 308.0,
        "rl_z20": 210.0,
        "ll_z20": 208.5,
        "trunk_z20": 42.0,
        "ra_z100": 290.0,
        "la_z100": 287.0,
        "rl_z100": 195.0,
        "ll_z100": 193.0,
        "trunk_z100": 38.0,
    }
    resp = client.post(
        "/api/measurements",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["bmi"] is not None, "bmi must be computed even when body_fat_pct=0.0"
    expected_bmi = round(80.0 / (1.75**2), 1)
    assert abs(data["bmi"] - expected_bmi) < 0.5
