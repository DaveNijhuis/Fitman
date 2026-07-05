"""entrypoint.sh behaviour tests (#133).

Uses subprocess with fake alembic/uvicorn binaries injected via PATH so the
real database is never touched.
"""

import os
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).parent.parent


def _run(tmp_path: Path, alembic_exit: int) -> subprocess.CompletedProcess:
    fake_alembic = tmp_path / "alembic"
    fake_alembic.write_text(f"#!/bin/sh\nexit {alembic_exit}\n")
    fake_alembic.chmod(0o755)

    marker = tmp_path / "uvicorn_called"
    fake_uvicorn = tmp_path / "uvicorn"
    fake_uvicorn.write_text(f"#!/bin/sh\ntouch {marker}\n")
    fake_uvicorn.chmod(0o755)

    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ.get('PATH', '')}"}
    return subprocess.run(
        ["sh", "entrypoint.sh"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_entrypoint_exits_nonzero_when_migration_fails(tmp_path):
    """A failing migration must produce a non-zero exit code."""
    result = _run(tmp_path, alembic_exit=1)
    assert result.returncode != 0


def test_entrypoint_does_not_start_uvicorn_when_migration_fails(tmp_path):
    """uvicorn must not be invoked when the migration fails."""
    _run(tmp_path, alembic_exit=1)
    assert not (tmp_path / "uvicorn_called").exists()


def test_entrypoint_prints_error_message_when_migration_fails(tmp_path):
    """A clear error message must appear when the migration fails.

    The current entrypoint silently exits via set -e with no message —
    this fails because combined stdout+stderr contains no 'error' context.
    """
    result = _run(tmp_path, alembic_exit=1)
    combined = result.stdout + result.stderr
    assert "error" in combined.lower() and "migration" in combined.lower(), (
        f"No clear error message found.\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


def test_entrypoint_starts_uvicorn_when_migration_succeeds(tmp_path):
    """When migration succeeds, uvicorn must be invoked."""
    _run(tmp_path, alembic_exit=0)
    assert (tmp_path / "uvicorn_called").exists()
