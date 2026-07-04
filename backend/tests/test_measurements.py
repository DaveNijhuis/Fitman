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
    assert isinstance(resp.json(), list)


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
