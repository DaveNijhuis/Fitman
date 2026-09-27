"""Migration adding the expanded exercise library (#356).

seed_exercises returns as soon as any exercise exists, so exercises added to
seed.py alone never reach a running install. The migration carries them
there; the seed carries them to a fresh one. Both must end up the same.

Runs the migration's own downgrade and upgrade against the real schema inside
a transaction that is rolled back — PostgreSQL DDL and DML are transactional.
"""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from database import engine
from seed import EXERCISES as SEED_EXERCISES

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "m9n1o3p5q7r9"
COLUMNS = ("name", "muscles", "type", "equip")


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


def _library(conn) -> dict[str, tuple]:
    rows = conn.execute(
        text("SELECT id, name, muscles, type, equip FROM exercises")
    ).all()
    return {r.name: tuple(r) for r in rows}


def _run(conn, step) -> None:
    with Operations.context(MigrationContext.configure(conn)):
        step()


def test_it_follows_session_templates_on_the_main_line():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert len(scripts.get_heads()) == 1
    assert REVISION in {r.revision for r in scripts.walk_revisions()}
    assert _migration().down_revision == "l8m0n2o4p6q8"


def test_it_adds_twenty_one_exercises_with_new_names():
    new = _migration().EXERCISES
    assert len(new) == 21
    assert len({e["name"] for e in new}) == 21


def test_upgrade_adds_exactly_the_new_exercises_and_touches_nothing_else():
    mod = _migration()
    new_names = {e["name"] for e in mod.EXERCISES}
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            _run(conn, mod.downgrade)
            before = _library(conn)
            assert new_names.isdisjoint(before)

            _run(conn, mod.upgrade)
            after = _library(conn)

            assert set(after) - set(before) == new_names
            assert {n: after[n] for n in before} == before
            for e in mod.EXERCISES:
                assert after[e["name"]][1:] == tuple(e[c] for c in COLUMNS)
        finally:
            trans.rollback()


def test_running_the_upgrade_again_adds_nothing():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            once = _library(conn)
            _run(conn, mod.upgrade)
            assert _library(conn) == once
        finally:
            trans.rollback()


def test_a_fresh_install_is_left_to_the_seed():
    """With no library yet, adding these would make the seed skip the rest."""
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("DELETE FROM logs"))
            conn.execute(text("DELETE FROM template_exercises"))
            conn.execute(text("DELETE FROM exercises"))
            _run(conn, mod.upgrade)
            assert (
                conn.execute(text("SELECT count(*) FROM exercises")).scalar_one() == 0
            )
        finally:
            trans.rollback()


def test_downgrade_keeps_an_exercise_that_has_been_logged():
    """Removing it would take the user's sets with it; FK or not, never do that."""
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            user_id = conn.execute(
                text("SELECT id FROM users WHERE username = 'testuser'")
            ).scalar_one()
            workout = conn.execute(
                text(
                    "INSERT INTO workout_sessions (user_id, session, started_at) "
                    "VALUES (:u, 'Pull A', :t) RETURNING id"
                ),
                {"u": user_id, "t": datetime.now(timezone.utc)},
            ).scalar_one()
            chin_up = conn.execute(
                text("SELECT id FROM exercises WHERE name = 'Chin-Up'")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO logs (exercise_id, session_id, weight, reps, logged_at) "
                    "VALUES (:e, :s, 0, 8, :t)"
                ),
                {"e": chin_up, "s": workout, "t": datetime.now(timezone.utc)},
            )

            _run(conn, mod.downgrade)

            left = _library(conn)
            assert "Chin-Up" in left
            assert {e["name"] for e in mod.EXERCISES} & set(left) == {"Chin-Up"}
        finally:
            trans.rollback()


def test_a_fresh_install_and_an_upgraded_one_have_the_same_library():
    """The seed's list is the original library plus exactly the migration's."""
    seed = {e["name"]: tuple(e[c] for c in COLUMNS) for e in SEED_EXERCISES}
    added = {e["name"]: tuple(e[c] for c in COLUMNS) for e in _migration().EXERCISES}
    assert {n: seed[n] for n in added if n in seed} == added
    assert len(seed) == 20 + len(added)
