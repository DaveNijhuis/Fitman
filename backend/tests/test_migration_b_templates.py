"""Migration adding Push B, Pull B and Legs B (#357).

The B days follow Legacy Muscle's dumbbell-only 6-day PPL, mapped onto the
library: seven exercises it needs are new, the rest already exist — some in
an A day, so their history is shared. Colours follow the category, not A/B.

Runs the migration's own downgrade and upgrade against the real schema inside
a transaction that is rolled back.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from seed import EXERCISES as SEED_EXERCISES
from seed import TEMPLATES as SEED_TEMPLATES
from tests.builtin import builtin_exercises, builtin_id
from tests.migrations import step_down_through

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "n0o2p4q6r8s0"
COLUMNS = ("name", "muscles", "type", "equip")

B_DAYS = {
    "Push B": (
        "#ff5a36",
        [
            "Arnold Press",
            "DB Front Raise",
            "Push-Up",
            "DB Pullover",
            "DB Skull Crusher",
        ],
    ),
    "Pull B": (
        "#3b82f6",
        ["DB High Row", "Renegade Row", "DB Shrug", "DB Curl", "DB Reverse Curl"],
    ),
    "Legs B": (
        "#1f9d62",
        [
            "DB Goblet Squat",
            "DB Stiff-Legged Deadlift",
            "DB Lateral Lunge",
            "DB Hip Thrust",
            "Seated DB Calf Raise",
        ],
    ),
}
NEW_EXERCISES = {
    "DB Front Raise",
    "DB High Row",
    "Renegade Row",
    "DB Curl",
    "DB Reverse Curl",
    "DB Stiff-Legged Deadlift",
    "DB Lateral Lunge",
}


@pytest.fixture(autouse=True)
def _schema(client) -> None:
    """Needs the schema built and seeded, which the app's startup does."""


def _migration(revision: str = REVISION):
    path = next((BACKEND / "alembic" / "versions").glob(f"{revision}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{revision}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(conn, step) -> None:
    with Operations.context(MigrationContext.configure(conn)):
        step()


def _library(conn) -> dict[str, tuple]:
    rows = conn.execute(
        text("SELECT id, name, muscles, type, equip FROM exercises")
    ).all()
    return {r.name: tuple(r) for r in rows}


def _built_ins(conn) -> list[tuple]:
    """(name, colour, [exercise names in order]) per built-in, in display order."""
    templates = conn.execute(
        text(
            "SELECT id, name, colour FROM session_templates "
            "WHERE user_id IS NULL ORDER BY position, id"
        )
    ).all()
    return [
        (
            t.name,
            t.colour,
            [
                r.name
                for r in conn.execute(
                    text(
                        "SELECT e.name FROM template_exercises te "
                        "JOIN exercises e ON e.id = te.exercise_id "
                        "WHERE te.template_id = :t ORDER BY te.position"
                    ),
                    {"t": t.id},
                )
            ],
        )
        for t in templates
    ]


def test_it_follows_the_library_expansion_on_the_main_line():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert len(scripts.get_heads()) == 1
    assert REVISION in {r.revision for r in scripts.walk_revisions()}
    assert _migration().down_revision == "m9n1o3p5q7r9"


def test_upgrade_adds_the_b_days_after_the_a_days_and_touches_nothing_else():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            step_down_through(conn, REVISION)
            library_before = _library(conn)
            templates_before = _built_ins(conn)
            assert NEW_EXERCISES.isdisjoint(library_before)
            assert [t[0] for t in templates_before] == ["Push A", "Pull A", "Legs A"]

            _run(conn, mod.upgrade)

            library_after = _library(conn)
            assert set(library_after) - set(library_before) == NEW_EXERCISES
            assert {n: library_after[n] for n in library_before} == library_before
            for e in mod.EXERCISES:
                assert library_after[e["name"]][1:] == tuple(e[c] for c in COLUMNS)

            templates_after = _built_ins(conn)
            assert templates_after[:3] == templates_before
            assert templates_after[3:] == [
                (name, colour, exercises)
                for name, (colour, exercises) in B_DAYS.items()
            ]
        finally:
            trans.rollback()


def test_each_b_day_shares_its_categorys_colour():
    with engine.connect() as conn:
        colours = {name: colour for name, colour, _ in _built_ins(conn)}
    for day in ("Push", "Pull", "Legs"):
        assert colours[f"{day} B"] == colours[f"{day} A"]


def test_running_the_upgrade_again_adds_nothing():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            library, templates = _library(conn), _built_ins(conn)
            _run(conn, mod.upgrade)
            assert _library(conn) == library
            assert _built_ins(conn) == templates
        finally:
            trans.rollback()


def test_a_fresh_install_is_left_to_the_seed():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("DELETE FROM logs"))
            conn.execute(text("DELETE FROM template_exercises"))
            conn.execute(text("DELETE FROM session_templates"))
            conn.execute(text("DELETE FROM exercises"))
            _run(conn, mod.upgrade)
            assert (
                conn.execute(text("SELECT count(*) FROM exercises")).scalar_one() == 0
            )
            assert (
                conn.execute(
                    text("SELECT count(*) FROM session_templates")
                ).scalar_one()
                == 0
            )
        finally:
            trans.rollback()


def test_a_fresh_install_and_an_upgraded_one_have_the_same_library_and_days():
    """The seed is the original library plus exactly what #356 and #357 add."""
    seed = {e["name"]: tuple(e[c] for c in COLUMNS) for e in SEED_EXERCISES}
    added = {
        e["name"]: tuple(e[c] for c in COLUMNS)
        for e in _migration("m9n1o3p5q7r9").EXERCISES + _migration().EXERCISES
    }
    assert {n: seed[n] for n in added if n in seed} == added
    assert len(seed) == 20 + len(added)

    seeded_days = {t["name"]: (t["colour"], t["exercises"]) for t in SEED_TEMPLATES}
    assert list(seeded_days)[3:] == list(B_DAYS)
    assert {n: seeded_days[n] for n in B_DAYS} == B_DAYS


def test_an_exercise_in_an_a_and_a_b_day_keeps_one_history(client: TestClient):
    push_up_a = next(e for e in builtin_exercises("Push A") if e["name"] == "Push-Up")
    push_up_b = next(e for e in builtin_exercises("Push B") if e["name"] == "Push-Up")
    assert push_up_a["id"] == push_up_b["id"]
    assert builtin_id("Push B") != builtin_id("Push A")
