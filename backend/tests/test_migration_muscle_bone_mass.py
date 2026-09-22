"""Migration adding muscle and bone mass to body_measurements (#344).

The test database is built with create_all, so the model alone would pass
every other test even with no migration at all. This runs the migration's own
downgrade and upgrade against the real schema inside a transaction that is
rolled back — PostgreSQL DDL is transactional.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from database import engine

BACKEND = Path(__file__).resolve().parents[1]
REVISION = "k7l9m1n3o5p6"
COLUMNS = {"muscle_mass_kg", "bone_mass_kg"}


@pytest.fixture(autouse=True)
def _schema(database: None) -> None:
    """Needs the schema built; nothing here goes through the HTTP client."""


def _migration():
    path = next((BACKEND / "alembic" / "versions").glob(f"{REVISION}_*.py"))
    spec = importlib.util.spec_from_file_location(f"migration_{REVISION}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_is_the_single_head_after_scale_user_id():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert scripts.get_heads() == [REVISION]
    assert _migration().down_revision == "j6k8l0m2n4o5"


def test_downgrade_then_upgrade_round_trips():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            with Operations.context(MigrationContext.configure(conn)):
                mod.downgrade()
                names = {
                    c["name"] for c in inspect(conn).get_columns("body_measurements")
                }
                assert not COLUMNS & names
                mod.upgrade()
            cols = {
                c["name"]: c for c in inspect(conn).get_columns("body_measurements")
            }
            for name in COLUMNS:
                assert cols[name]["nullable"] is True, name
        finally:
            trans.rollback()
