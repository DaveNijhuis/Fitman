from fastapi.testclient import TestClient


def _token(client: TestClient) -> str:
    return client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    ).json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


# ── GET /api/profile ──────────────────────────────────────────────────────────


def test_profile_returns_correct_structure(client: TestClient):
    resp = client.get("/api/profile", headers=_auth(client))
    assert resp.status_code == 200
    data = resp.json()
    for key in ("username", "display_name", "birth_year", "sex", "height_cm", "email"):
        assert key in data


def test_profile_requires_auth(client: TestClient):
    from fastapi.testclient import TestClient as TC

    from main import app

    c = TC(app)
    assert c.get("/api/profile").status_code == 401


# ── PATCH /api/profile ────────────────────────────────────────────────────────


def test_patch_profile_updates_display_name(client: TestClient):
    resp = client.patch(
        "/api/profile", json={"display_name": "Dave Test"}, headers=_auth(client)
    )
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "Dave Test"


def test_patch_profile_updates_height(client: TestClient):
    resp = client.patch(
        "/api/profile", json={"height_cm": 182.0}, headers=_auth(client)
    )
    assert resp.status_code == 200
    assert resp.json()["height_cm"] == 182.0


def test_patch_profile_updates_birth_year(client: TestClient):
    resp = client.patch(
        "/api/profile", json={"birth_year": 1990}, headers=_auth(client)
    )
    assert resp.status_code == 200
    assert resp.json()["birth_year"] == 1990


def test_patch_profile_updates_sex(client: TestClient):
    resp = client.patch("/api/profile", json={"sex": "male"}, headers=_auth(client))
    assert resp.status_code == 200
    assert resp.json()["sex"] == "male"


def test_patch_profile_ignores_unknown_fields(client: TestClient):
    resp = client.patch(
        "/api/profile", json={"nonexistent_field": "value"}, headers=_auth(client)
    )
    assert resp.status_code == 200


# ── Input validation (#181) ───────────────────────────────────────────────────


def test_patch_sex_invalid_value_returns_422(client: TestClient):
    resp = client.patch("/api/profile", json={"sex": "banana"}, headers=_auth(client))
    assert resp.status_code == 422


def test_patch_sex_empty_string_returns_422(client: TestClient):
    resp = client.patch("/api/profile", json={"sex": ""}, headers=_auth(client))
    assert resp.status_code == 422


def test_patch_sex_accepts_all_valid_values(client: TestClient):
    headers = _auth(client)
    for value in ("male", "female", "other"):
        resp = client.patch("/api/profile", json={"sex": value}, headers=headers)
        assert resp.status_code == 200, (
            f"Expected 200 for sex={value!r}, got {resp.status_code}"
        )
        assert resp.json()["sex"] == value


def test_patch_birth_year_below_minimum_returns_422(client: TestClient):
    resp = client.patch(
        "/api/profile", json={"birth_year": 1899}, headers=_auth(client)
    )
    assert resp.status_code == 422


def test_patch_birth_year_negative_returns_422(client: TestClient):
    resp = client.patch("/api/profile", json={"birth_year": -1}, headers=_auth(client))
    assert resp.status_code == 422


def test_patch_birth_year_future_returns_422(client: TestClient):
    from datetime import datetime

    future_year = datetime.now().year + 1
    resp = client.patch(
        "/api/profile", json={"birth_year": future_year}, headers=_auth(client)
    )
    assert resp.status_code == 422


def test_patch_birth_year_minimum_boundary_valid(client: TestClient):
    resp = client.patch(
        "/api/profile", json={"birth_year": 1900}, headers=_auth(client)
    )
    assert resp.status_code == 200
    assert resp.json()["birth_year"] == 1900


def test_patch_birth_year_current_year_valid(client: TestClient):
    from datetime import datetime

    current_year = datetime.now().year
    resp = client.patch(
        "/api/profile", json={"birth_year": current_year}, headers=_auth(client)
    )
    assert resp.status_code == 200
    assert resp.json()["birth_year"] == current_year


# ── Profile fields used as BIA fallback ───────────────────────────────────────


def test_bia_uses_profile_height_when_not_in_request(client: TestClient):
    """Set height_cm in profile; BIA payload without height_cm must still run formulae."""
    headers = _auth(client)
    client.patch(
        "/api/profile",
        json={"height_cm": 180.0, "birth_year": 1996, "sex": "male"},
        headers=headers,
    )

    resp = client.post(
        "/api/measurements",
        json={
            "weight_kg": 80.0,
            "body_fat_pct": 18.2,
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
        },
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["bmi"] is not None
