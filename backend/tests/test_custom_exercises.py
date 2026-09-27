"""Custom exercises with open-ended equipment (#358).

A user adds their own exercises to the library, with any equipment — cable,
machine, band — as free text. They see the built-ins plus their own and never
another user's, anywhere an exercise can be reached. Deleting one that has
been logged archives it instead: hidden from the library, history intact.
"""

from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.exercise import Exercise
from models.user import User
from tests.builtin import builtin_exercises


def _auth(client: TestClient, username: str) -> dict:
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == username).first():
            db.add(
                User(
                    username=username,
                    hashed_password=bcrypt.hashpw(
                        b"password1", bcrypt.gensalt(rounds=4)
                    ).decode(),
                    is_active=True,
                    is_admin=False,
                    created_at=datetime.now(timezone.utc),
                )
            )
            db.commit()
    finally:
        db.close()
    token = client.post(
        "/api/auth/login", json={"username": username, "password": "password1"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create(client: TestClient, headers: dict, **overrides) -> dict:
    body = {
        "name": "Cable Fly",
        "muscles": "Chest",
        "type": "weight",
        "equip": "Cable",
    } | overrides
    resp = client.post("/api/exercises", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _names(client: TestClient, headers: dict, query: str = "") -> list[str]:
    return [
        e["name"] for e in client.get(f"/api/exercises{query}", headers=headers).json()
    ]


def _log(client: TestClient, headers: dict, exercise_id: int) -> int:
    """Start a Push A workout and log one set; the response status."""
    template_id = next(
        t["id"]
        for t in client.get("/api/templates", headers=headers).json()
        if t["name"] == "Push A"
    )
    workout = client.post(
        "/api/sessions", json={"template_id": template_id}, headers=headers
    ).json()
    return client.post(
        "/api/logs",
        json={
            "session_id": workout["id"],
            "exercise_id": exercise_id,
            "weight": 20.0,
            "reps": 10,
        },
        headers=headers,
    ).status_code


# ── Creating ──────────────────────────────────────────────────────────────────


def test_a_user_adds_an_exercise_with_any_equipment(client: TestClient):
    headers = _auth(client, "cx_create")
    made = _create(
        client, headers, name="Leg Press", muscles="Quads, Glutes", equip="Machine"
    )
    assert made["name"] == "Leg Press"
    assert made["equip"] == "Machine"
    assert made["custom"] is True
    assert made["archived"] is False
    assert "Leg Press" in _names(client, headers)


def test_built_ins_say_they_are_not_custom(client: TestClient):
    headers = _auth(client, "cx_builtin_flag")
    listed = client.get("/api/exercises", headers=headers).json()
    bench = next(e for e in listed if e["name"] == "Flat DB Bench Press")
    assert bench["custom"] is False


def test_equipment_is_trimmed_and_reuses_the_existing_spelling(client: TestClient):
    """ "  dumbbell " is the Dumbbell filter, not a second one beside it."""
    headers = _auth(client, "cx_equip")
    made = _create(client, headers, name="DB Tate Press", equip="  dumbbell ")
    assert made["equip"] == "Dumbbell"


def test_new_equipment_keeps_its_own_spelling_trimmed(client: TestClient):
    headers = _auth(client, "cx_equip_new")
    made = _create(client, headers, name="Band Pull-Apart", equip="  Resistance Band ")
    assert made["equip"] == "Resistance Band"


def test_the_equipment_list_offers_whats_in_use_for_this_user(client: TestClient):
    headers = _auth(client, "cx_equip_list")
    _create(client, headers, name="Smith Squat", equip="Smith Machine")
    theirs = _auth(client, "cx_equip_list_other")
    _create(client, theirs, name="Their Sled Push", equip="Sled")

    equipment = client.get("/api/exercises/equipment", headers=headers).json()
    assert "Smith Machine" in equipment
    assert "Dumbbell" in equipment and "Bodyweight" in equipment
    assert "Sled" not in equipment
    assert equipment == sorted(equipment, key=str.lower)


def test_the_library_filters_by_equipment_ignoring_case(client: TestClient):
    headers = _auth(client, "cx_equip_filter")
    _create(client, headers, name="Lat Pulldown", equip="Cable")
    names = _names(client, headers, "?equip=cable")
    assert names == ["Lat Pulldown"]


def test_a_name_already_in_the_library_is_refused(client: TestClient):
    headers = _auth(client, "cx_dupe")
    resp = client.post(
        "/api/exercises",
        json={
            "name": " push-up ",
            "muscles": None,
            "type": "bodyweight",
            "equip": "Bodyweight",
        },
        headers=headers,
    )
    assert resp.status_code == 409


def test_blank_name_or_equipment_and_unknown_type_are_refused(client: TestClient):
    headers = _auth(client, "cx_invalid")
    for body in (
        {"name": "  ", "muscles": None, "type": "weight", "equip": "Cable"},
        {"name": "Thing", "muscles": None, "type": "weight", "equip": "  "},
        {"name": "Thing", "muscles": None, "type": "cardio", "equip": "Cable"},
    ):
        assert (
            client.post("/api/exercises", json=body, headers=headers).status_code == 422
        )


# ── Isolation ─────────────────────────────────────────────────────────────────


def test_another_users_exercise_is_unreachable_everywhere(client: TestClient):
    mine = _auth(client, "cx_iso_owner")
    made = _create(client, mine, name="Owner's Hack Squat", equip="Machine")
    other = _auth(client, "cx_iso_other")

    assert "Owner's Hack Squat" not in _names(client, other)
    assert client.get(f"/api/exercises/{made['id']}", headers=other).status_code == 404
    assert _log(client, other, made["id"]) == 404
    strength = client.get(
        f"/api/progress/strength?exercise_id={made['id']}", headers=other
    )
    assert strength.status_code == 404
    edit = client.patch(
        f"/api/exercises/{made['id']}", json={"name": "Mine now"}, headers=other
    )
    assert edit.status_code == 404
    assert (
        client.delete(f"/api/exercises/{made['id']}", headers=other).status_code == 404
    )


def test_the_owner_can_log_and_chart_their_exercise(client: TestClient):
    headers = _auth(client, "cx_log_owner")
    made = _create(client, headers, name="Pec Deck", equip="Machine")
    assert _log(client, headers, made["id"]) == 201
    data = client.get(
        f"/api/progress/strength?exercise_id={made['id']}", headers=headers
    ).json()
    assert data["exercise_name"] == "Pec Deck"
    assert len(data["data"]) == 1


# ── Editing ───────────────────────────────────────────────────────────────────


def test_the_owner_edits_their_exercise(client: TestClient):
    headers = _auth(client, "cx_edit")
    made = _create(client, headers, name="Cable Crossover")
    resp = client.patch(
        f"/api/exercises/{made['id']}",
        json={"name": "High Cable Crossover", "equip": " cable "},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "High Cable Crossover"
    assert resp.json()["equip"] == "Cable"
    assert resp.json()["muscles"] == "Chest"


def test_built_in_exercises_cannot_be_edited_or_deleted(client: TestClient):
    headers = _auth(client, "cx_builtin_ro")
    bench = builtin_exercises("Push A")[0]
    assert (
        client.patch(
            f"/api/exercises/{bench['id']}", json={"name": "Mine"}, headers=headers
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/exercises/{bench['id']}", headers=headers).status_code
        == 403
    )
    assert builtin_exercises("Push A")[0] == bench


# ── Deleting and archiving ────────────────────────────────────────────────────


def test_deleting_an_unlogged_exercise_removes_it(client: TestClient):
    headers = _auth(client, "cx_delete")
    made = _create(client, headers, name="Hip Abduction", equip="Machine")
    assert (
        client.delete(f"/api/exercises/{made['id']}", headers=headers).status_code
        == 204
    )
    assert (
        client.get(f"/api/exercises/{made['id']}", headers=headers).status_code == 404
    )
    db = SessionLocal()
    try:
        assert db.get(Exercise, made["id"]) is None
    finally:
        db.close()


def test_deleting_a_logged_exercise_archives_it_and_keeps_its_history(
    client: TestClient,
):
    headers = _auth(client, "cx_archive")
    made = _create(client, headers, name="T-Bar Row", muscles="Lats", equip="Landmine")
    assert _log(client, headers, made["id"]) == 201

    assert (
        client.delete(f"/api/exercises/{made['id']}", headers=headers).status_code
        == 204
    )

    assert "T-Bar Row" not in _names(client, headers)
    assert (
        "Landmine" not in client.get("/api/exercises/equipment", headers=headers).json()
    )
    detail = client.get(f"/api/exercises/{made['id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["archived"] is True
    history = client.get(
        f"/api/progress/strength?exercise_id={made['id']}", headers=headers
    )
    assert len(history.json()["data"]) == 1
    prs = client.get("/api/progress/prs", headers=headers).json()
    assert "T-Bar Row" in {p["exercise_name"] for p in prs}


def test_an_archived_exercise_takes_no_new_sets(client: TestClient):
    headers = _auth(client, "cx_archive_log")
    made = _create(client, headers, name="Reverse Hyper", equip="Machine")
    assert _log(client, headers, made["id"]) == 201
    client.delete(f"/api/exercises/{made['id']}", headers=headers)
    assert _log(client, headers, made["id"]) == 409


def test_an_archived_name_can_be_used_again(client: TestClient):
    headers = _auth(client, "cx_archive_name")
    made = _create(client, headers, name="Hammer Strength Row", equip="Machine")
    _log(client, headers, made["id"])
    client.delete(f"/api/exercises/{made['id']}", headers=headers)
    again = _create(client, headers, name="Hammer Strength Row", equip="Machine")
    assert again["id"] != made["id"]


# ── Your data ─────────────────────────────────────────────────────────────────


def test_the_export_includes_custom_exercises(client: TestClient):
    headers = _auth(client, "cx_export")
    _create(
        client,
        headers,
        name="Ab Wheel Rollout",
        muscles=None,
        type="bodyweight",
        equip="Ab Wheel",
    )
    exported = client.get("/api/gdpr/export", headers=headers).json()
    names = [e["name"] for e in exported["custom_exercises"]]
    assert names == ["Ab Wheel Rollout"]
    assert exported["custom_exercises"][0]["equip"] == "Ab Wheel"


def test_erasing_an_account_removes_its_exercises_and_their_sets(client: TestClient):
    headers = _auth(client, "cx_erase")
    made = _create(
        client, headers, name="Sissy Squat", equip="Bodyweight", type="bodyweight"
    )
    assert _log(client, headers, made["id"]) == 201

    assert client.delete("/api/gdpr/erase", headers=headers).status_code == 204

    db = SessionLocal()
    try:
        assert db.get(Exercise, made["id"]) is None
    finally:
        db.close()


def test_an_admin_can_delete_a_user_who_logged_a_custom_exercise(client: TestClient):
    """The same two cascades as erasing, from the admin side."""
    headers = _auth(client, "cx_admin_target")
    made = _create(client, headers, name="Belt Squat", equip="Machine")
    assert _log(client, headers, made["id"]) == 201
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.username == "cx_admin_target").one().id
    finally:
        db.close()
    admin = {
        "Authorization": "Bearer "
        + client.post(
            "/api/auth/login", json={"username": "testuser", "password": "testpass"}
        ).json()["access_token"]
    }

    assert client.delete(f"/api/admin/users/{target}", headers=admin).status_code == 204

    db = SessionLocal()
    try:
        assert db.get(Exercise, made["id"]) is None
    finally:
        db.close()


def test_a_template_filter_combines_with_equipment(client: TestClient):
    """Push A holds dumbbell and bodyweight work; asking for one narrows it."""
    headers = _auth(client, "cx_tpl_equip")
    push_a = next(
        t["id"]
        for t in client.get("/api/templates", headers=headers).json()
        if t["name"] == "Push A"
    )
    names = _names(client, headers, f"?template_id={push_a}&equip=bodyweight")
    assert names == ["Push-Up", "Chest Dip"]


def test_an_edit_can_clear_the_muscles(client: TestClient):
    headers = _auth(client, "cx_clear_muscles")
    made = _create(client, headers, name="Sled Drag", muscles="Quads", equip="Sled")
    resp = client.patch(
        f"/api/exercises/{made['id']}", json={"muscles": "  "}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["muscles"] is None
    assert resp.json()["name"] == "Sled Drag"
