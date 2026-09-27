"""Session templates: the exercise library decoupled from sessions (#354).

An exercise used to belong to exactly one session through a text column, so
Pull-Up could not sit in both Pull A and Pull B without a second row — and a
second row splits its logs, chart and records across two exercise ids.
Templates point into a flat library instead, and built-ins (user_id NULL)
live beside user-owned ones.
"""

from datetime import datetime, timezone

import bcrypt
from fastapi.testclient import TestClient

from database import SessionLocal
from models.exercise import Exercise
from models.template import SessionTemplate, TemplateExercise
from models.user import User
from models.workout import WorkoutSession
from seed import seed_exercises

BUILT_INS = {
    "Push A": ("Chest · Shoulders · Triceps", "#ff5a36"),
    "Pull A": ("Back · Biceps · Rear Delts", "#3b82f6"),
    "Legs A": ("Quads · Glutes · Hamstrings", "#1f9d62"),
}


def _user(username: str) -> int:
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(
            username=username,
            hashed_password=bcrypt.hashpw(
                b"password1", bcrypt.gensalt(rounds=4)
            ).decode(),
            is_active=True,
            is_admin=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
    user_id = user.id
    db.close()
    return user_id


def _auth(client: TestClient, username: str = "testuser") -> dict:
    password = "testpass" if username == "testuser" else "password1"
    if username != "testuser":
        _user(username)
    token = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _own_template(owner: str, name: str, exercise_names: list[str]) -> int:
    """A user-owned template, made directly: the API to create one is #359."""
    owner_id = _user(owner)
    db = SessionLocal()
    template = SessionTemplate(
        name=name, focus=None, colour=None, position=0, user_id=owner_id
    )
    db.add(template)
    db.flush()
    for position, exercise_name in enumerate(exercise_names):
        exercise = db.query(Exercise).filter(Exercise.name == exercise_name).one()
        db.add(
            TemplateExercise(
                template_id=template.id, exercise_id=exercise.id, position=position
            )
        )
    db.commit()
    template_id = template.id
    db.close()
    return template_id


def _built_in_id(client: TestClient, name: str) -> int:
    templates = client.get("/api/templates", headers=_auth(client)).json()
    return next(t["id"] for t in templates if t["name"] == name)


# ── Listing ───────────────────────────────────────────────────────────────────


def test_lists_the_three_built_ins_in_order_with_focus_and_colour(client: TestClient):
    resp = client.get("/api/templates", headers=_auth(client))
    assert resp.status_code == 200
    built_ins = [t for t in resp.json() if t["builtin"]]
    assert [t["name"] for t in built_ins] == list(BUILT_INS)
    for t in built_ins:
        assert (t["focus"], t["colour"]) == BUILT_INS[t["name"]]


def test_requires_authentication(client: TestClient):
    assert client.get("/api/templates").status_code == 401


def test_template_detail_lists_its_exercises_in_order(client: TestClient):
    push_a = _built_in_id(client, "Push A")
    resp = client.get(f"/api/templates/{push_a}", headers=_auth(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Push A"
    names = [e["name"] for e in body["exercises"]]
    assert names[0] == "Flat DB Bench Press"
    assert names[-1] == "Chest Dip"
    assert len(names) == 7


def test_unknown_template_is_404(client: TestClient):
    resp = client.get("/api/templates/999999", headers=_auth(client))
    assert resp.status_code == 404


# ── Ownership ─────────────────────────────────────────────────────────────────


def test_another_users_template_is_invisible(client: TestClient):
    theirs = _own_template("tpl_owner_b", "B's Chest Day", ["Flat DB Bench Press"])
    headers = _auth(client)

    listed = client.get("/api/templates", headers=headers).json()
    assert theirs not in {t["id"] for t in listed}
    assert client.get(f"/api/templates/{theirs}", headers=headers).status_code == 404


def test_owner_sees_their_own_template_after_the_built_ins(client: TestClient):
    mine = _own_template("tpl_owner_c", "C's Arm Day", ["DB Hammer Curl"])
    listed = client.get("/api/templates", headers=_auth(client, "tpl_owner_c")).json()
    assert [t["name"] for t in listed[:3]] == list(BUILT_INS)
    own = next(t for t in listed if t["id"] == mine)
    assert own["builtin"] is False


# ── Starting a workout ────────────────────────────────────────────────────────


def test_start_by_template_id(client: TestClient):
    pull_a = _built_in_id(client, "Pull A")
    resp = client.post(
        "/api/sessions", json={"template_id": pull_a}, headers=_auth(client)
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["session"] == "Pull A"
    assert body["template_id"] == pull_a


def test_start_from_unknown_template_is_404(client: TestClient):
    resp = client.post(
        "/api/sessions", json={"template_id": 999999}, headers=_auth(client)
    )
    assert resp.status_code == 404


def test_start_from_another_users_template_is_404_and_stores_nothing(
    client: TestClient,
):
    theirs = _own_template("tpl_owner_d", "D's Back Day", ["One-Arm DB Row"])
    db = SessionLocal()
    before = db.query(WorkoutSession).count()
    db.close()

    resp = client.post(
        "/api/sessions", json={"template_id": theirs}, headers=_auth(client)
    )
    assert resp.status_code == 404

    db = SessionLocal()
    assert db.query(WorkoutSession).count() == before
    db.close()


def test_start_needs_a_template_id(client: TestClient):
    resp = client.post("/api/sessions", json={}, headers=_auth(client))
    assert resp.status_code == 422


def test_filtering_the_library_by_another_users_template_is_404(client: TestClient):
    theirs = _own_template("tpl_owner_g", "G's Chest Day", ["Flat DB Bench Press"])
    resp = client.get(f"/api/exercises?template_id={theirs}", headers=_auth(client))
    assert resp.status_code == 404


# ── One exercise, many templates ──────────────────────────────────────────────


def test_an_exercise_shared_by_two_templates_keeps_one_history(client: TestClient):
    """The point of the refactor: Pull-Up in two days is still one series."""
    user = "tpl_owner_e"
    headers = _auth(client, user)
    mine = _own_template(user, "E's Pull Day", ["Pull-Up"])
    pull_a = _built_in_id(client, "Pull A")

    pull_up = client.get(f"/api/templates/{mine}", headers=headers).json()["exercises"][
        0
    ]["id"]
    pull_a_ids = [
        e["id"]
        for e in client.get(f"/api/templates/{pull_a}", headers=headers).json()[
            "exercises"
        ]
    ]
    assert pull_up in pull_a_ids

    for template_id, weight in ((pull_a, 10.0), (mine, 30.0)):
        workout = client.post(
            "/api/sessions", json={"template_id": template_id}, headers=headers
        ).json()
        client.post(
            "/api/logs",
            json={
                "session_id": workout["id"],
                "exercise_id": pull_up,
                "weight": weight,
                "reps": 1,
            },
            headers=headers,
        )

    data = client.get(
        f"/api/progress/strength?exercise_id={pull_up}", headers=headers
    ).json()["data"]
    assert [p["estimated_1rm"] for p in data] == [30.0]


# ── Deleting a template ───────────────────────────────────────────────────────


def test_deleting_a_template_keeps_its_workouts_and_exercises(client: TestClient):
    user = "tpl_owner_f"
    headers = _auth(client, user)
    mine = _own_template(user, "F's Leg Day", ["DB Goblet Squat"])
    workout = client.post(
        "/api/sessions", json={"template_id": mine}, headers=headers
    ).json()

    db = SessionLocal()
    db.delete(db.get(SessionTemplate, mine))
    db.commit()

    kept = db.get(WorkoutSession, workout["id"])
    assert kept is not None
    assert kept.template_id is None
    assert kept.session == "F's Leg Day"
    assert (
        db.query(TemplateExercise).filter(TemplateExercise.template_id == mine).count()
        == 0
    )
    assert db.query(Exercise).filter(Exercise.name == "DB Goblet Squat").count() == 1
    db.close()


# ── Seed ──────────────────────────────────────────────────────────────────────


def test_seeding_again_adds_nothing(client: TestClient):
    db = SessionLocal()
    before = (
        db.query(Exercise).count(),
        db.query(SessionTemplate).count(),
        db.query(TemplateExercise).count(),
    )
    seed_exercises(db)
    after = (
        db.query(Exercise).count(),
        db.query(SessionTemplate).count(),
        db.query(TemplateExercise).count(),
    )
    db.close()
    assert after == before


def test_seed_builds_templates_when_the_exercises_already_exist(client: TestClient):
    """Exercises present but no built-in templates: seed fills in the templates.

    seed_exercises commits, so this really replaces the built-ins; later tests
    look templates up by name, never by a remembered id.
    """
    db = SessionLocal()
    exercises_before = db.query(Exercise).count()
    db.query(SessionTemplate).filter(SessionTemplate.user_id.is_(None)).delete()
    db.commit()

    seed_exercises(db)

    names = [
        t.name
        for t in db.query(SessionTemplate)
        .filter(SessionTemplate.user_id.is_(None))
        .order_by(SessionTemplate.position)
    ]
    assert names == list(BUILT_INS)
    assert db.query(Exercise).count() == exercises_before
    db.close()


# ── Progress calendar colour ──────────────────────────────────────────────────


def _trained_days(client: TestClient, headers: dict) -> list[dict]:
    weeks = client.get("/api/progress/consistency", headers=headers).json()
    return [d for w in weeks for d in w["days"] if d["trained"]]


def test_a_calendar_day_carries_its_workouts_template_colour(client: TestClient):
    headers = _auth(client, "tpl_owner_h")
    workout = client.post(
        "/api/sessions",
        json={"template_id": _built_in_id(client, "Pull A")},
        headers=headers,
    ).json()
    client.patch(f"/api/sessions/{workout['id']}/end", headers=headers)

    [day] = _trained_days(client, headers)
    assert day["session"] == "Pull A"
    assert day["colour"] == "#3b82f6"


def test_a_workout_without_a_template_has_no_colour(client: TestClient):
    """Its template was deleted, or it predates templates and matched no name."""
    user_id = _user("tpl_owner_i")
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    db.add(
        WorkoutSession(user_id=user_id, session="Old Day", started_at=now, ended_at=now)
    )
    db.commit()
    db.close()

    [day] = _trained_days(client, _auth(client, "tpl_owner_i"))
    assert day["session"] == "Old Day"
    assert day["colour"] is None
