"""Migration for user-made days (#359): workout exercise lists, hidden built-ins.

A workout now keeps the exercise list it started with, so editing its day
can't change it. Existing workouts get the list their template has now — the
closest record there is — and any in progress keeps working unchanged.

Runs against the real schema inside a transaction that is rolled back.
"""

from datetime import datetime, timezone

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from database import engine
from tests.migrations import BACKEND, step_down_through

REVISION = "p2q4r6s8t0u2"


@pytest.fixture(autouse=True)
def _schema(client) -> None:
    """Needs the schema built and seeded, which the app's startup does."""


def _migration():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    return scripts.get_revision(REVISION).module


def test_it_follows_custom_exercises_on_the_main_line():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert len(scripts.get_heads()) == 1
    assert _migration().down_revision == "o1p3q5r7s9t1"


def test_upgrade_gives_every_templated_workout_its_templates_list():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_through(conn, REVISION)
            assert not inspect(conn).has_table("workout_exercises")
            assert not inspect(conn).has_table("hidden_templates")

            now = datetime.now(timezone.utc)
            user = conn.execute(
                text("SELECT id FROM users WHERE username = 'testuser'")
            ).scalar_one()
            legs_a = conn.execute(
                text(
                    "SELECT id FROM session_templates "
                    "WHERE user_id IS NULL AND name = 'Legs A'"
                )
            ).scalar_one()
            in_progress = conn.execute(
                text(
                    "INSERT INTO workout_sessions (user_id, session, template_id, started_at) "
                    "VALUES (:u, 'Legs A', :t, :s) RETURNING id"
                ),
                {"u": user, "t": legs_a, "s": now},
            ).scalar_one()
            untemplated = conn.execute(
                text(
                    "INSERT INTO workout_sessions (user_id, session, started_at, ended_at) "
                    "VALUES (:u, 'Old Day', :s, :s) RETURNING id"
                ),
                {"u": user, "s": now},
            ).scalar_one()

            with Operations.context(MigrationContext.configure(conn)):
                _migration().upgrade()

            def listed(workout: int) -> list[int]:
                return [
                    r[0]
                    for r in conn.execute(
                        text(
                            "SELECT exercise_id FROM workout_exercises "
                            "WHERE workout_session_id = :w ORDER BY position"
                        ),
                        {"w": workout},
                    )
                ]

            legs_a_list = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT exercise_id FROM template_exercises "
                        "WHERE template_id = :t ORDER BY position"
                    ),
                    {"t": legs_a},
                )
            ]
            assert listed(in_progress) == legs_a_list
            assert listed(untemplated) == []

            unlisted = conn.execute(
                text(
                    "SELECT count(*) FROM workout_sessions w WHERE w.template_id IS NOT NULL "
                    "AND NOT EXISTS (SELECT 1 FROM workout_exercises x "
                    "WHERE x.workout_session_id = w.id)"
                )
            ).scalar_one()
            assert unlisted == 0
            assert inspect(conn).has_table("hidden_templates")
        finally:
            trans.rollback()


def test_downgrade_drops_both_tables():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_through(conn, REVISION)
            assert not inspect(conn).has_table("workout_exercises")
            assert not inspect(conn).has_table("hidden_templates")
        finally:
            trans.rollback()
