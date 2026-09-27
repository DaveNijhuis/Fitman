"""Migration from exercises.session to session templates (#354).

The test database is built with create_all, so the models alone would pass
every other test with no migration at all. This runs the migration's own
downgrade and upgrade against the real schema inside a transaction that is
rolled back — PostgreSQL DDL is transactional.

The downgrade puts the schema back in the old shape; the test then adds a
workout and a log the old way, and checks the upgrade carries every one of
them over: same exercise ids, same order per session, every workout linked
to its template by name.
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from database import engine
from tests.migrations import step_down_through, step_down_to

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "l8m0n2o4p6q8"


@pytest.fixture(autouse=True)
def _schema(client) -> None:
    """Needs the schema built and seeded, which the app's startup does."""


def _migration():
    path = next((BACKEND / "alembic" / "versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{REVISION}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_follows_muscle_and_bone_mass_on_the_main_line():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert len(scripts.get_heads()) == 1
    assert REVISION in {r.revision for r in scripts.walk_revisions()}
    assert _migration().down_revision == "k7l9m1n3o5p6"


def _columns(conn, table: str) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns(table)}


def test_upgrade_turns_each_session_into_a_template_and_loses_nothing():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_through(conn, REVISION)
            with Operations.context(MigrationContext.configure(conn)):
                assert {"session", "position"} <= _columns(conn, "exercises")
                assert "template_id" not in _columns(conn, "workout_sessions")
                assert not inspect(conn).has_table("session_templates")
                assert not inspect(conn).has_table("template_exercises")

                # Exercises in no template (other tests make some) come back
                # with an empty session, and the upgrade makes no template of it.
                old_order = conn.execute(
                    text(
                        "SELECT session, id FROM exercises WHERE session <> '' "
                        "ORDER BY session, position"
                    )
                ).all()
                user_id = conn.execute(
                    text("SELECT id FROM users WHERE username = 'testuser'")
                ).scalar_one()
                workout_id = conn.execute(
                    text(
                        "INSERT INTO workout_sessions (user_id, session, started_at) "
                        "VALUES (:u, 'Pull A', :t) RETURNING id"
                    ),
                    {"u": user_id, "t": datetime.now(timezone.utc)},
                ).scalar_one()
                pull_up = conn.execute(
                    text("SELECT id FROM exercises WHERE name = 'Pull-Up'")
                ).scalar_one()
                conn.execute(
                    text(
                        "INSERT INTO logs (exercise_id, session_id, weight, reps, logged_at) "
                        "VALUES (:e, :s, 0, 10, :t)"
                    ),
                    {"e": pull_up, "s": workout_id, "t": datetime.now(timezone.utc)},
                )
                logs_before = conn.execute(
                    text("SELECT count(*) FROM logs")
                ).scalar_one()
                orphan_workouts = conn.execute(
                    text(
                        "SELECT count(*) FROM workout_sessions "
                        "WHERE session NOT IN ('Push A', 'Pull A', 'Legs A')"
                    )
                ).scalar_one()

                mod.upgrade()

            assert {"session", "position"}.isdisjoint(_columns(conn, "exercises"))

            templates = conn.execute(
                text(
                    "SELECT name, focus, colour FROM session_templates "
                    "WHERE user_id IS NULL ORDER BY position"
                )
            ).all()
            assert [tuple(t) for t in templates] == [
                ("Push A", "Chest · Shoulders · Triceps", "#ff5a36"),
                ("Pull A", "Back · Biceps · Rear Delts", "#3b82f6"),
                ("Legs A", "Quads · Glutes · Hamstrings", "#1f9d62"),
            ]

            new_order = conn.execute(
                text(
                    "SELECT t.name, te.exercise_id FROM template_exercises te "
                    "JOIN session_templates t ON t.id = te.template_id "
                    "ORDER BY t.name, te.position"
                )
            ).all()
            assert [tuple(r) for r in new_order] == [tuple(r) for r in old_order]

            linked = conn.execute(
                text(
                    "SELECT t.name FROM workout_sessions w "
                    "JOIN session_templates t ON t.id = w.template_id WHERE w.id = :w"
                ),
                {"w": workout_id},
            ).scalar_one()
            assert linked == "Pull A"

            unlinked = conn.execute(
                text("SELECT count(*) FROM workout_sessions WHERE template_id IS NULL")
            ).scalar_one()
            assert unlinked == orphan_workouts

            assert (
                conn.execute(text("SELECT count(*) FROM logs")).scalar_one()
                == logs_before
            )
        finally:
            trans.rollback()


def test_downgrade_restores_each_exercises_session_and_position():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_to(conn, REVISION)
            before = conn.execute(
                text(
                    "SELECT te.exercise_id, t.name, te.position FROM template_exercises te "
                    "JOIN session_templates t ON t.id = te.template_id "
                    "WHERE t.user_id IS NULL ORDER BY te.exercise_id"
                )
            ).all()
            with Operations.context(MigrationContext.configure(conn)):
                mod.downgrade()
            after = conn.execute(
                text("SELECT id, session, position FROM exercises ORDER BY id")
            ).all()
            in_a_template = [
                tuple(r) for r in after if r.id in {b.exercise_id for b in before}
            ]
            assert in_a_template == [tuple(r) for r in before]
            assert all(r.session == "" for r in after if tuple(r) not in in_a_template)
        finally:
            trans.rollback()
