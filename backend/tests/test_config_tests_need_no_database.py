"""Config-only tests must run without a database (#283).

conftest.py built and seeded the schema at module import, so pytest opened a
connection during collection and every test needed a reachable PostgreSQL —
including the twelve files that only read YAML, .gitignore and compose files.
Checking a lint-config assertion should not require starting Docker.

The database is pointed at a port nothing listens on rather than mocked: the
failure mode being guarded against is a real connection attempt, and a mock
would prove only that the mock was not called.
"""

import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Config-only modules: no client fixture, no SessionLocal, no engine.
_CONFIG_ONLY = [
    "tests/test_ci_playwright_pin.py",
    "tests/test_ci_security_scanning.py",
    "tests/test_compose_config.py",
    "tests/test_compose_launch.py",
    "tests/test_compose_ports.py",
    "tests/test_db_volume_guard.py",
    "tests/test_dockerignore.py",
    "tests/test_frontend_dockerignore.py",
    "tests/test_gitignore.py",
    "tests/test_lint_config.py",
    "tests/test_nginx_conf.py",
    "tests/test_prod_db_credentials.py",
    "tests/test_readme_https.py",
    "tests/test_scale_handshake.py",
    "tests/test_scale_protocol.py",
]

# Nothing listens here, so any connection attempt fails immediately rather than
# hanging on a network timeout.
_UNREACHABLE = "postgresql://nobody:nobody@127.0.0.1:1/fitman_test"


def _run(args: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": database_url}
    return subprocess.run(  # noqa: S603 — args come from _CONFIG_ONLY above, not input
        [
            sys.executable,
            "-m",
            "pytest",
            *args,
            "--no-header",
            "--no-cov",
            "-p",
            "no:cacheprovider",
        ],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_config_only_tests_pass_with_no_database_reachable() -> None:
    result = _run(_CONFIG_ONLY, _UNREACHABLE)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        "config-only tests still require a database:\n" + combined[-2000:]
    )


def test_collection_does_not_open_a_connection() -> None:
    """Collection alone must not touch the database.

    A connection at import time is what forced every test to need one, so the
    guard is on collection specifically rather than on a passing run.
    """
    result = _run(["--collect-only", "-q", *_CONFIG_ONLY], _UNREACHABLE)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        "collection opened a database connection:\n" + combined[-2000:]
    )
    assert "OperationalError" not in combined
    assert "could not connect" not in combined.lower()


def test_database_backed_tests_still_run() -> None:
    """The regression guard: making the connection lazy must not skip it."""
    result = _run(["tests/test_health.py"], os.environ["DATABASE_URL"])
    assert result.returncode == 0, (
        "database-backed tests broke:\n" + (result.stdout + result.stderr)[-2000:]
    )
