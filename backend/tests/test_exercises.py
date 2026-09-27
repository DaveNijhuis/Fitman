from fastapi.testclient import TestClient

from tests.builtin import builtin_exercises, builtin_id


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


# ── Filtering by template ─────────────────────────────────────────────────────


def test_template_filter_returns_its_exercises_in_order(client: TestClient):
    legs_a = builtin_id("Legs A")
    resp = client.get(f"/api/exercises?template_id={legs_a}", headers=_auth(client))
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()]
    assert names[0] == "DB Goblet Squat"
    assert names[-1] == "Single-Leg Calf Raise"
    assert len(names) == 6


def test_template_filter_combines_with_search(client: TestClient):
    """The Library sends both: a template tab and the search box.

    "DB" matches exercises in every template, so only the template filter can
    narrow it to these two.
    """
    legs_a = builtin_id("Legs A")
    resp = client.get(
        f"/api/exercises?template_id={legs_a}&search=db", headers=_auth(client)
    )
    assert resp.status_code == 200
    assert [e["name"] for e in resp.json()] == ["DB Goblet Squat", "DB Reverse Lunge"]


def test_unknown_template_filter_is_404(client: TestClient):
    resp = client.get("/api/exercises?template_id=999999", headers=_auth(client))
    assert resp.status_code == 404


# ── #354's name-based bridge is gone ──────────────────────────────────────────


def test_the_session_names_endpoint_is_gone(client: TestClient):
    """/sessions now falls through to /{exercise_id}, which wants an integer."""
    resp = client.get("/api/exercises/sessions", headers=_auth(client))
    assert resp.status_code == 422


def test_the_session_name_filter_is_ignored(client: TestClient):
    """An unknown query parameter filters nothing: the whole library comes back."""
    headers = _auth(client)
    everything = client.get("/api/exercises", headers=headers).json()
    resp = client.get("/api/exercises?session=Legs+A", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == everything


# ── Exercise list ─────────────────────────────────────────────────────────────


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
    exercise_id = builtin_exercises("Push A")[0]["id"]
    resp = client.get(f"/api/exercises/{exercise_id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == exercise_id
    assert "name" in data
    # An exercise sits in any number of templates now, not one session (#354).
    assert "session" not in data
    assert "position" not in data


def test_get_exercise_by_id_not_found(client: TestClient):
    resp = client.get("/api/exercises/999999", headers=_auth(client))
    assert resp.status_code == 404
