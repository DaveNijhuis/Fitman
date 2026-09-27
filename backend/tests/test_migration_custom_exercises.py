"""Migration for custom exercises (#358): owner, archive, deferred keys.

Runs the migration's own downgrade and upgrade against the real schema inside
a transaction that is rolled back.
"""

from datetime import datetime, timezone

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from database import engine
from tests.migrations import BACKEND, step_down_through, step_down_to

REVISION = "o1p3q5r7s9t1"
KEYS = ("logs_exercise_id_fkey", "template_exercises_exercise_id_fkey")


@pytest.fixture(autouse=True)
def _schema(client) -> None:
    """Needs the schema built and seeded, which the app's startup does."""


def _migration():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    return scripts.get_revision(REVISION).module


def _deferrable(conn) -> dict[str, bool]:
    rows = conn.execute(
        text(
            "SELECT conname, condeferrable AND condeferred FROM pg_constraint "
            "WHERE conname = ANY(:names)"
        ),
        {"names": list(KEYS)},
    ).all()
    return dict(rows)


def _columns(conn) -> set[str]:
    return {c["name"] for c in inspect(conn).get_columns("exercises")}


def test_it_follows_the_b_days_on_the_main_line():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert len(scripts.get_heads()) == 1
    assert _migration().down_revision == "n0o2p4q6r8s0"


def test_upgrade_adds_owner_and_archive_and_defers_the_keys_into_exercises():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_through(conn, REVISION)
            assert {"user_id", "archived_at"}.isdisjoint(_columns(conn))
            assert _deferrable(conn) == {k: False for k in KEYS}

            with Operations.context(MigrationContext.configure(conn)):
                _migration().upgrade()

            assert {"user_id", "archived_at"} <= _columns(conn)
            assert _deferrable(conn) == {k: True for k in KEYS}
            custom = conn.execute(
                text("SELECT count(*) FROM exercises WHERE user_id IS NOT NULL")
            ).scalar_one()
            assert custom == 0
        finally:
            trans.rollback()


def test_erasing_a_user_with_a_logged_custom_exercise_works_after_upgrading():
    """The cascade the deferred keys exist for, on the migrated schema."""
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_through(conn, REVISION)
            with Operations.context(MigrationContext.configure(conn)):
                _migration().upgrade()

            now = datetime.now(timezone.utc)
            user = conn.execute(
                text(
                    "INSERT INTO users (username, hashed_password, is_active, "
                    "is_admin, created_at, token_version) "
                    "VALUES ('mig_erase', 'x', true, false, :t, 0) RETURNING id"
                ),
                {"t": now},
            ).scalar_one()
            exercise = conn.execute(
                text(
                    "INSERT INTO exercises (user_id, name, type, equip) "
                    "VALUES (:u, 'Mig Row', 'weight', 'Cable') RETURNING id"
                ),
                {"u": user},
            ).scalar_one()
            workout = conn.execute(
                text(
                    "INSERT INTO workout_sessions (user_id, session, started_at) "
                    "VALUES (:u, 'Pull A', :t) RETURNING id"
                ),
                {"u": user, "t": now},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO logs (exercise_id, session_id, weight, reps, logged_at) "
                    "VALUES (:e, :w, 20, 8, :t)"
                ),
                {"e": exercise, "w": workout, "t": now},
            )

            conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user})
            conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))  # the commit's check

            gone = conn.execute(
                text("SELECT count(*) FROM exercises WHERE id = :e"), {"e": exercise}
            ).scalar_one()
            assert gone == 0
        finally:
            trans.rollback()


def test_downgrade_removes_custom_exercises_and_their_sets_only():
    """The old shape has no owner: custom rows can't stay without leaking."""
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_to(conn, REVISION)
            now = datetime.now(timezone.utc)
            user = conn.execute(
                text("SELECT id FROM users WHERE username = 'testuser'")
            ).scalar_one()
            exercise = conn.execute(
                text(
                    "INSERT INTO exercises (user_id, name, type, equip) "
                    "VALUES (:u, 'Mig Fly', 'weight', 'Cable') RETURNING id"
                ),
                {"u": user},
            ).scalar_one()
            workout = conn.execute(
                text(
                    "INSERT INTO workout_sessions (user_id, session, started_at) "
                    "VALUES (:u, 'Push A', :t) RETURNING id"
                ),
                {"u": user, "t": now},
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO logs (exercise_id, session_id, weight, reps, logged_at) "
                    "VALUES (:e, :w, 20, 8, :t)"
                ),
                {"e": exercise, "w": workout, "t": now},
            )
            built_in_logs = conn.execute(
                text(
                    "SELECT count(*) FROM logs l JOIN exercises e ON e.id = l.exercise_id "
                    "WHERE e.user_id IS NULL"
                )
            ).scalar_one()

            with Operations.context(MigrationContext.configure(conn)):
                _migration().downgrade()

            assert {"user_id", "archived_at"}.isdisjoint(_columns(conn))
            assert _deferrable(conn) == {k: False for k in KEYS}
            assert (
                conn.execute(
                    text("SELECT count(*) FROM exercises WHERE id = :e"),
                    {"e": exercise},
                ).scalar_one()
                == 0
            )
            assert conn.execute(text("SELECT count(*) FROM logs")).scalar_one() == (
                built_in_logs
            )
        finally:
            trans.rollback()
