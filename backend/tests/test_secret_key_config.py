"""SECRET_KEY must be read as a typed str without breaking startup diagnostics (#222).

os.getenv("SECRET_KEY") is typed str | None, so mypy cannot see that PyJWT
would be handed None. Reading it via os.environ makes the type str — but it
must not move the failure ahead of main.py's operator-facing startup check.
"""

import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _import_main_without_secret_key(cwd: Path) -> subprocess.CompletedProcess[str]:
    """Import main with SECRET_KEY absent, from a directory holding no .env."""
    env = {k: v for k, v in os.environ.items() if k != "SECRET_KEY"}
    env["PYTHONPATH"] = str(BACKEND_DIR)
    env.setdefault(
        "DATABASE_URL", "postgresql://fitman:fitman@localhost:5432/fitman_test"
    )
    return subprocess.run(
        [sys.executable, "-c", "import main"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def test_auth_reads_secret_key_from_environ():
    """os.environ[...] is typed str; os.getenv(...) is str | None."""
    source = (BACKEND_DIR / "auth.py").read_text()
    assert 'os.environ["SECRET_KEY"]' in source


def test_auth_does_not_use_getenv_for_secret_key():
    source = (BACKEND_DIR / "auth.py").read_text()
    assert 'os.getenv("SECRET_KEY")' not in source


def test_missing_secret_key_still_reports_the_friendly_startup_error(tmp_path):
    """Regression guard: main.py's check must win over any import-time KeyError.

    routers.auth is imported at main.py:22, well before the _REQUIRED guard at
    line 73. A module-level os.environ["SECRET_KEY"] in auth.py would therefore
    raise first and replace the operator-facing message with a raw traceback.
    """
    result = _import_main_without_secret_key(tmp_path)
    combined = result.stdout + result.stderr
    assert "Missing required environment variables: SECRET_KEY" in combined, (
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert "KeyError" not in combined, (
        f"startup diagnostics regressed to a traceback:\n{combined}"
    )
