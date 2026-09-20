"""pytest must refuse to run against a non-test database (#248).

conftest.py calls Base.metadata.drop_all(engine) at import time against
whatever DATABASE_URL resolves to. It uses os.environ.setdefault, so the safe
fitman_test default applies only when the variable is unset — and the README
development instructions tell you to export DATABASE_URL for `alembic upgrade
head` and `fastapi dev`. Running pytest in that same shell silently drops every
table in the working database.

These tests point a real pytest run at a scratch database holding a table and
assert both that the run refuses and that the table is still there afterwards.
The second assertion is the one that matters: an exit code alone would not
prove the data survived.
"""

import os
import subprocess
import sys
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy import create_engine, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_SCRATCH_DB = "fitman_guard_probe"
# A real application table. Base.metadata.drop_all only drops tables it knows
# about, so a canary of our own invention would survive regardless and prove
# nothing — this has to be a table conftest would actually destroy.
_CANARY_TABLE = "users"
_CANARY_USER = "irreplaceable"


def _admin_url() -> str:
    """The configured server, pointed at the default maintenance database."""
    parts = urlsplit(os.environ["DATABASE_URL"])
    return urlunsplit(parts._replace(path="/postgres"))


def _url_for(database: str) -> str:
    parts = urlsplit(os.environ["DATABASE_URL"])
    return urlunsplit(parts._replace(path=f"/{database}"))


@pytest.fixture
def scratch_database() -> Iterator[str]:
    """A database whose name does not end in _test, holding one table."""
    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_SCRATCH_DB}"))
        conn.execute(text(f"CREATE DATABASE {_SCRATCH_DB}"))
    admin.dispose()

    # Build the real application schema, so this database looks exactly like a
    # developer's working database rather than an empty shell.
    from database import Base

    target = create_engine(_url_for(_SCRATCH_DB), isolation_level="AUTOCOMMIT")
    Base.metadata.create_all(target)
    with target.connect() as conn:
        conn.execute(
            text(
                # noqa placement must match the reported line.
                f"INSERT INTO {_CANARY_TABLE} "  # noqa: S608 — table name from a module constant
                "(username, hashed_password, is_active, is_admin, "
                "created_at, token_version) "
                "VALUES (:canary, 'x', true, true, now(), 0)"
            ),
            {"canary": _CANARY_USER},
        )
    target.dispose()

    yield _url_for(_SCRATCH_DB)

    admin = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {_SCRATCH_DB}"))
    admin.dispose()


def _run_pytest_against(url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": url}
    return subprocess.run(
        # --no-cov: the project sets --cov-fail-under=90 in addopts, and a
        # single-file run would exit non-zero on coverage alone, masking
        # whether the guard actually fired.
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_health.py",
            "--no-header",
            "--no-cov",
            "-x",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def _canary_survives(url: str) -> bool:
    """Looks for the specific row, not a count.

    conftest drops the table, recreates it and seeds its own user, so both
    "table exists" and "one row present" are true afterwards either way. Only
    the original row's identity distinguishes a run that was blocked from one
    that wiped the database and refilled it."""
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            if not conn.execute(
                text("SELECT to_regclass(:name)"), {"name": _CANARY_TABLE}
            ).scalar():
                return False
            return bool(
                conn.execute(
                    text(
                        f"SELECT 1 FROM {_CANARY_TABLE} WHERE username = :u"  # noqa: S608 — table name from a module constant
                    ),
                    {"u": _CANARY_USER},
                ).scalar()
            )
    finally:
        engine.dispose()


def test_run_is_refused_against_a_non_test_database(scratch_database: str) -> None:
    result = _run_pytest_against(scratch_database)
    assert result.returncode != 0, (
        "pytest ran against a database whose name does not end in _test"
    )


def test_refusal_names_the_database_it_declined_to_touch(
    scratch_database: str,
) -> None:
    result = _run_pytest_against(scratch_database)
    combined = result.stdout + result.stderr
    assert _SCRATCH_DB in combined, (
        f"error does not name the database:\n{combined[-1500:]}"
    )


def test_the_data_survives(scratch_database: str) -> None:
    """The point of the guard. An exit code alone proves nothing."""
    _run_pytest_against(scratch_database)
    assert _canary_survives(scratch_database), (
        f"the {_CANARY_USER!r} row was destroyed — the guard did not prevent data loss"
    )


def test_a_test_database_is_still_accepted() -> None:
    """The guard must not break the normal case."""
    result = _run_pytest_against(os.environ["DATABASE_URL"])
    assert result.returncode == 0, (
        f"pytest refused the configured test database:\n{(result.stdout + result.stderr)[-1500:]}"
    )
