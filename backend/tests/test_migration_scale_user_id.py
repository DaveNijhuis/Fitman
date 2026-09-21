"""Migration adding users.scale_user_id (#323).

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
REVISION = "j6k8l0m2n4o5"


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


def test_it_is_the_single_head_after_token_version():
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    assert scripts.get_heads() == [REVISION]
    assert _migration().down_revision == "i5j7k9l1m3n4"


def test_downgrade_then_upgrade_round_trips():
    mod = _migration()
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            with Operations.context(MigrationContext.configure(conn)):
                mod.downgrade()
                assert "scale_user_id" not in {
                    c["name"] for c in inspect(conn).get_columns("users")
                }
                mod.upgrade()
            cols = {c["name"]: c for c in inspect(conn).get_columns("users")}
            assert cols["scale_user_id"]["nullable"] is True
            uniques = inspect(conn).get_unique_constraints("users")
            assert any(u["column_names"] == ["scale_user_id"] for u in uniques)
        finally:
            trans.rollback()
