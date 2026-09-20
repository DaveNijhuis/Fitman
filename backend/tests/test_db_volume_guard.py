"""The PostgreSQL data volume must be checked before postgres starts (#270).

An instance upgraded across the SQLite -> PostgreSQL migration still has
fitman.db sitting in the db_data volume, now mounted at the PostgreSQL data
directory. Postgres refuses to initdb over a non-empty directory and
restart-loops; backend and frontend both wait on service_healthy, so the whole
stack is dead. The error names initdb and a path, and says nothing about a
migration two milestones back.

The volume is deliberately NOT renamed: a rename creates a new empty volume,
so every instance already running PostgreSQL would come up healthy on an empty
database — trading a loud failure for a silent one.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_README = _ROOT / "README.md"
_COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")

_GUARD_SERVICE = "db-guard"


def _compose(name: str) -> dict[str, Any]:
    return yaml.safe_load((_ROOT / name).read_text())


@pytest.mark.parametrize("compose_file", _COMPOSE_FILES)
def test_guard_service_is_defined(compose_file: str) -> None:
    assert _GUARD_SERVICE in _compose(compose_file)["services"]


@pytest.mark.parametrize("compose_file", _COMPOSE_FILES)
def test_guard_mounts_the_postgres_volume(compose_file: str) -> None:
    """It can only inspect the volume if it mounts it."""
    guard = _compose(compose_file)["services"][_GUARD_SERVICE]
    assert any("db_data" in str(v) for v in guard.get("volumes", []))


@pytest.mark.parametrize("compose_file", _COMPOSE_FILES)
def test_postgres_waits_for_the_guard_to_succeed(compose_file: str) -> None:
    """A guard postgres does not wait on would report nothing in time."""
    postgres = _compose(compose_file)["services"]["postgres"]
    depends = postgres.get("depends_on", {})
    assert _GUARD_SERVICE in depends
    assert depends[_GUARD_SERVICE]["condition"] == "service_completed_successfully"


@pytest.mark.parametrize("compose_file", _COMPOSE_FILES)
def test_guard_names_the_stale_sqlite_file(compose_file: str) -> None:
    """The whole point is a message that explains the cause."""
    guard = _compose(compose_file)["services"][_GUARD_SERVICE]
    command = str(guard.get("command", ""))
    assert "fitman.db" in command


@pytest.mark.parametrize("compose_file", _COMPOSE_FILES)
def test_volume_is_not_renamed(compose_file: str) -> None:
    """Renaming creates an empty volume: existing instances would start blank."""
    compose = _compose(compose_file)
    assert "db_data" in compose["volumes"]
    assert any(
        "db_data:/var/lib/postgresql/data" in str(v)
        for v in compose["services"]["postgres"]["volumes"]
    )


def _migration_section() -> str:
    text = _README.read_text()
    start = text.index("### Migrating from SQLite")
    return text[start : text.index("### Backups", start)]


def test_migration_docs_explain_the_volume_conflict() -> None:
    """Neither documented path mentioned the volume that blocks the upgrade."""
    assert "db_data" in _migration_section()


def test_migration_docs_recover_the_file_from_the_volume() -> None:
    """Option B said to export from the old app, which can no longer start
    once the compose file has been replaced. The file must come out of the
    volume directly instead."""
    section = _migration_section()
    assert "docker run" in section and "fitman.db" in section


def test_migration_docs_do_not_tell_you_to_export_from_the_old_app() -> None:
    section = _migration_section()
    assert "/api/gdpr/export" not in section
