"""User-created session templates (#359).

A user builds their own days from the library — a chest day, a full-body
day — duplicates a built-in to start from, and hides built-ins they don't
use. A workout keeps the exercise list it started with, so editing or
deleting its template never changes a workout in progress or in History.
"""

from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.user import User
from tests.builtin import builtin_exercises, builtin_id


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


def _ids(*names: str) -> list[int]:
    library = {
        e["name"]: e["id"]
        for t in ("Push A", "Pull A", "Legs A", "Push B")
        for e in builtin_exercises(t)
    }
    return [library[n] for n in names]


def _create(client: TestClient, headers: dict, **overrides) -> dict:
    body = {
        "name": "Chest Day",
        "focus": "Chest · Triceps",
        "colour": "#ff5a36",
        "exercise_ids": _ids("Flat DB Bench Press", "Incline DB Press", "Chest Dip"),
    } | overrides
    resp = client.post("/api/templates", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _listed(client: TestClient, headers: dict) -> dict[str, dict]:
    return {t["name"]: t for t in client.get("/api/templates", headers=headers).json()}


def _start(client: TestClient, headers: dict, template_id: int) -> dict:
    resp = client.post(
        "/api/sessions", json={"template_id": template_id}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _workout_exercises(client: TestClient, headers: dict, workout_id: int) -> list[str]:
    resp = client.get(f"/api/sessions/{workout_id}/exercises", headers=headers)
    assert resp.status_code == 200, resp.text
    return [e["name"] for e in resp.json()]


# ── Creating ──────────────────────────────────────────────────────────────────


def test_a_user_builds_a_day_from_the_library_in_their_order(client: TestClient):
    headers = _auth(client, "ct_create")
    made = _create(client, headers)
    assert made["builtin"] is False
    assert made["hidden"] is False
    assert [e["name"] for e in made["exercises"]] == [
        "Flat DB Bench Press",
        "Incline DB Press",
        "Chest Dip",
    ]
    listed = _listed(client, headers)
    assert listed["Chest Day"]["colour"] == "#ff5a36"
    assert list(listed)[-1] == "Chest Day"


def test_a_day_can_hold_the_users_own_exercises(client: TestClient):
    headers = _auth(client, "ct_custom_ex")
    fly = client.post(
        "/api/exercises",
        json={"name": "Cable Fly", "type": "weight", "equip": "Cable"},
        headers=headers,
    ).json()
    made = _create(client, headers, exercise_ids=[fly["id"], *_ids("Push-Up")])
    assert [e["name"] for e in made["exercises"]] == ["Cable Fly", "Push-Up"]


def test_a_day_cannot_hold_another_users_or_an_archived_exercise(client: TestClient):
    theirs = _auth(client, "ct_ex_owner")
    their_ex = client.post(
        "/api/exercises",
        json={"name": "Their Pec Deck", "type": "weight", "equip": "Machine"},
        headers=theirs,
    ).json()
    headers = _auth(client, "ct_ex_thief")
    resp = client.post(
        "/api/templates",
        json={"name": "Stolen", "exercise_ids": [their_ex["id"]]},
        headers=headers,
    )
    assert resp.status_code == 422

    mine = client.post(
        "/api/exercises",
        json={"name": "Old Machine Row", "type": "weight", "equip": "Machine"},
        headers=headers,
    ).json()
    day = _create(client, headers, name="Uses Old Row", exercise_ids=[mine["id"]])
    client.delete(f"/api/exercises/{mine['id']}", headers=headers)  # archived: in a day
    resp = client.post(
        "/api/templates",
        json={"name": "Archived", "exercise_ids": [mine["id"]]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert day["id"]


def test_invalid_days_are_refused(client: TestClient):
    headers = _auth(client, "ct_invalid")
    bench = _ids("Flat DB Bench Press")
    for body in (
        {"name": "  ", "exercise_ids": bench},
        {"name": "Empty", "exercise_ids": []},
        {"name": "Twice", "exercise_ids": bench + bench},
        {"name": "Bad colour", "colour": "orange", "exercise_ids": bench},
    ):
        assert (
            client.post("/api/templates", json=body, headers=headers).status_code == 422
        )


def test_a_name_already_among_your_days_is_refused(client: TestClient):
    headers = _auth(client, "ct_dupe_name")
    _create(client, headers, name="Arm Day")
    for name in (" arm day ", "Push A"):
        resp = client.post(
            "/api/templates",
            json={"name": name, "exercise_ids": _ids("DB Hammer Curl")},
            headers=headers,
        )
        assert resp.status_code == 409


# ── Isolation and built-ins ───────────────────────────────────────────────────


def test_another_users_day_cannot_be_edited_deleted_duplicated_or_hidden(
    client: TestClient,
):
    theirs = _auth(client, "ct_iso_owner")
    made = _create(client, theirs, name="Their Day")
    headers = _auth(client, "ct_iso_other")
    tid = made["id"]
    assert (
        client.patch(
            f"/api/templates/{tid}", json={"name": "Mine"}, headers=headers
        ).status_code
        == 404
    )
    assert client.delete(f"/api/templates/{tid}", headers=headers).status_code == 404
    assert (
        client.post(f"/api/templates/{tid}/duplicate", headers=headers).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/templates/{tid}/hidden", json={"hidden": True}, headers=headers
        ).status_code
        == 404
    )
    assert _listed(client, theirs)["Their Day"]["name"] == "Their Day"


def test_built_ins_cannot_be_edited_or_deleted(client: TestClient):
    headers = _auth(client, "ct_builtin_ro")
    push_a = builtin_id("Push A")
    before = [e["id"] for e in builtin_exercises("Push A")]
    assert (
        client.patch(
            f"/api/templates/{push_a}", json={"name": "Mine"}, headers=headers
        ).status_code
        == 403
    )
    assert client.delete(f"/api/templates/{push_a}", headers=headers).status_code == 403
    assert [e["id"] for e in builtin_exercises("Push A")] == before


# ── Editing and deleting ──────────────────────────────────────────────────────


def test_the_owner_renames_and_reorders_their_day(client: TestClient):
    headers = _auth(client, "ct_edit")
    made = _create(client, headers)
    resp = client.patch(
        f"/api/templates/{made['id']}",
        json={
            "name": "Chest & Arms",
            "colour": "#8b5cf6",
            "exercise_ids": _ids("Chest Dip", "Flat DB Bench Press", "DB Hammer Curl"),
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Chest & Arms"
    assert body["colour"] == "#8b5cf6"
    assert body["focus"] == "Chest · Triceps"
    assert [e["name"] for e in body["exercises"]] == [
        "Chest Dip",
        "Flat DB Bench Press",
        "DB Hammer Curl",
    ]


def test_deleting_a_day_keeps_its_workouts_readable(client: TestClient):
    headers = _auth(client, "ct_delete")
    made = _create(client, headers, name="Leg Day Plus")
    workout = _start(client, headers, made["id"])
    client.patch(f"/api/sessions/{workout['id']}/end", headers=headers)

    assert (
        client.delete(f"/api/templates/{made['id']}", headers=headers).status_code
        == 204
    )

    assert "Leg Day Plus" not in _listed(client, headers)
    history = client.get("/api/sessions", headers=headers).json()
    kept = next(w for w in history if w["id"] == workout["id"])
    assert kept["session"] == "Leg Day Plus"
    assert kept["template_id"] is None
    assert _workout_exercises(client, headers, workout["id"]) == [
        "Flat DB Bench Press",
        "Incline DB Press",
        "Chest Dip",
    ]


# ── A workout keeps what it started with ─────────────────────────────────────


def test_editing_a_day_mid_workout_leaves_the_workout_as_it_started(
    client: TestClient,
):
    headers = _auth(client, "ct_midworkout")
    made = _create(client, headers)
    workout = _start(client, headers, made["id"])

    client.patch(
        f"/api/templates/{made['id']}",
        json={"exercise_ids": _ids("Push-Up")},
        headers=headers,
    )

    assert _workout_exercises(client, headers, workout["id"]) == [
        "Flat DB Bench Press",
        "Incline DB Press",
        "Chest Dip",
    ]
    fresh = _start(client, headers, made["id"])
    assert _workout_exercises(client, headers, fresh["id"]) == ["Push-Up"]


def test_a_workouts_exercises_are_its_owners_alone(client: TestClient):
    owner = _auth(client, "ct_wx_owner")
    workout = _start(client, owner, builtin_id("Pull A"))
    other = _auth(client, "ct_wx_other")
    resp = client.get(f"/api/sessions/{workout['id']}/exercises", headers=other)
    assert resp.status_code == 404


# ── Duplicating ───────────────────────────────────────────────────────────────


def test_duplicating_a_built_in_gives_an_independent_copy(client: TestClient):
    headers = _auth(client, "ct_duplicate")
    push_a = builtin_id("Push A")
    resp = client.post(f"/api/templates/{push_a}/duplicate", headers=headers)
    assert resp.status_code == 201, resp.text
    copy = resp.json()
    assert copy["name"] == "Push A (copy)"
    assert copy["builtin"] is False
    assert copy["colour"] == "#ff5a36"
    assert [e["id"] for e in copy["exercises"]] == [
        e["id"] for e in builtin_exercises("Push A")
    ]

    client.patch(
        f"/api/templates/{copy['id']}",
        json={"exercise_ids": _ids("Push-Up")},
        headers=headers,
    )
    assert len(builtin_exercises("Push A")) == 7

    again = client.post(f"/api/templates/{push_a}/duplicate", headers=headers).json()
    assert again["name"] == "Push A (copy 2)"


# ── Hiding built-ins ──────────────────────────────────────────────────────────


def test_hiding_a_built_in_is_per_user_and_can_be_undone(client: TestClient):
    headers = _auth(client, "ct_hide")
    legs_b = builtin_id("Legs B")
    resp = client.put(
        f"/api/templates/{legs_b}/hidden", json={"hidden": True}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["hidden"] is True
    assert _listed(client, headers)["Legs B"]["hidden"] is True

    other = _auth(client, "ct_hide_other")
    assert _listed(client, other)["Legs B"]["hidden"] is False

    # Still startable: hiding tidies Home, it doesn't take the day away.
    _start(client, headers, legs_b)

    client.put(
        f"/api/templates/{legs_b}/hidden", json={"hidden": False}, headers=headers
    )
    assert _listed(client, headers)["Legs B"]["hidden"] is False


def test_only_built_ins_are_hidden_your_own_are_deleted(client: TestClient):
    headers = _auth(client, "ct_hide_own")
    made = _create(client, headers, name="Own Day")
    resp = client.put(
        f"/api/templates/{made['id']}/hidden", json={"hidden": True}, headers=headers
    )
    assert resp.status_code == 422


# ── Exercises in use ──────────────────────────────────────────────────────────


def test_deleting_an_exercise_a_workout_started_with_archives_it(client: TestClient):
    """The workout's list still points at it, even with no set logged yet."""
    headers = _auth(client, "ct_ex_in_workout")
    row = client.post(
        "/api/exercises",
        json={"name": "Seal Row Machine", "type": "weight", "equip": "Machine"},
        headers=headers,
    ).json()
    day = _create(client, headers, name="Row Day", exercise_ids=[row["id"]])
    workout = _start(client, headers, day["id"])
    client.delete(f"/api/templates/{day['id']}", headers=headers)

    assert (
        client.delete(f"/api/exercises/{row['id']}", headers=headers).status_code == 204
    )
    assert (
        client.get(f"/api/exercises/{row['id']}", headers=headers).json()["archived"]
        is True
    )
    assert _workout_exercises(client, headers, workout["id"]) == ["Seal Row Machine"]


# ── Your data ─────────────────────────────────────────────────────────────────


def test_the_export_includes_your_days_and_hidden_built_ins(client: TestClient):
    headers = _auth(client, "ct_export")
    _create(client, headers, name="Export Day")
    client.put(
        f"/api/templates/{builtin_id('Pull B')}/hidden",
        json={"hidden": True},
        headers=headers,
    )
    exported = client.get("/api/gdpr/export", headers=headers).json()
    [day] = exported["templates"]
    assert day["name"] == "Export Day"
    assert day["exercises"] == ["Flat DB Bench Press", "Incline DB Press", "Chest Dip"]
    assert exported["hidden_templates"] == ["Pull B"]


def test_erasing_an_account_removes_its_days(client: TestClient):
    headers = _auth(client, "ct_erase")
    fly = client.post(
        "/api/exercises",
        json={"name": "Erase Fly", "type": "weight", "equip": "Cable"},
        headers=headers,
    ).json()
    made = _create(client, headers, name="Erase Day", exercise_ids=[fly["id"]])
    _start(client, headers, made["id"])
    client.put(
        f"/api/templates/{builtin_id('Push B')}/hidden",
        json={"hidden": True},
        headers=headers,
    )

    assert client.delete("/api/gdpr/erase", headers=headers).status_code == 204
    fresh = _auth(client, "ct_erase_check")
    assert "Erase Day" not in _listed(client, fresh)


def test_an_edit_sets_or_clears_the_focus_and_refuses_a_blank_name(
    client: TestClient,
):
    headers = _auth(client, "ct_edit_focus")
    made = _create(client, headers, name="Focus Day")
    url = f"/api/templates/{made['id']}"

    assert client.patch(url, json={"name": "  "}, headers=headers).status_code == 422
    changed = client.patch(url, json={"focus": " Arms  · Chest "}, headers=headers)
    assert changed.json()["focus"] == "Arms · Chest"
    cleared = client.patch(url, json={"focus": None, "name": None}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["focus"] is None
    assert cleared.json()["name"] == "Focus Day"
