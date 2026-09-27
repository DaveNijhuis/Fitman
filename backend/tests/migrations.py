"""Stepping a migration test's database down the way Alembic would.

A migration's test runs its downgrade on the test database, which is built at
head. Running that one downgrade alone skips every later migration and leaves
a state no real database reaches: #357's B days still pointing at exercises
#356's downgrade is meant to remove, say. Stepping down through each later
migration first, newest to oldest, is what `alembic downgrade` does.
"""

from pathlib import Path

from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection

BACKEND = Path(__file__).resolve().parents[1]


def _step_down(conn: Connection, revision: str, *, including: bool) -> None:
    scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
    with Operations.context(MigrationContext.configure(conn)):
        for script in scripts.walk_revisions():  # head first
            if script.revision == revision and not including:
                return
            script.module.downgrade()
            if script.revision == revision:
                return
    raise AssertionError(f"{revision} is not on the main line")


def step_down_to(conn: Connection, revision: str) -> None:
    """Undo every migration newer than `revision`: the database as it just ran."""
    _step_down(conn, revision, including=False)


def step_down_through(conn: Connection, revision: str) -> None:
    """Undo every migration from head down to and including `revision`."""
    _step_down(conn, revision, including=True)
