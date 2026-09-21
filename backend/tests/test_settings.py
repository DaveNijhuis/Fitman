"""Environment configuration is validated once, in one place (#250).

Twelve variables were read across six modules in four styles: a raw KeyError at
import (DATABASE_URL), a lazy KeyError (SECRET_KEY), bare int()/float() casts
whose ValueError never named the variable (DB_POOL_SIZE, JWT_EXPIRE_DAYS,
SCALE_*), and a friendly check in main.py that covered SECRET_KEY only and ran
after the routers had been imported. A bad deploy failed on the first problem
it happened to hit, one per restart.

These tests pin the replacement: a Settings object in config.py that reports
every problem together, by variable name, before anything else runs.
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from config import ENV_FILE, Settings, load_settings

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent

FITMAN_VARS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "JWT_EXPIRE_DAYS",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_TIMEOUT",
    "CORS_ORIGINS",
    "FITMAN_LOG_FORMAT",
    "RATE_LIMIT_DISABLED",
    "SCALE_HEIGHT_CM",
    "SCALE_AGE",
    "SCALE_SEX",
]

_REQUIRED = {
    "SECRET_KEY": "test-secret",
    "DATABASE_URL": "postgresql://fitman:fitman@localhost:5432/fitman_test",
}


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """No Fitman variable set, so each test states exactly what it relies on."""
    for name in FITMAN_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def required_env(clean_env: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name, value in _REQUIRED.items():
        clean_env.setenv(name, value)
    return clean_env


def _problems() -> str:
    """The startup message produced by load_settings for this environment."""
    with pytest.raises(SystemExit) as exc:
        load_settings(env_file=None)
    assert exc.value.code != 0
    return str(exc.value.code)


# ── Defaults ──────────────────────────────────────────────────────────────────


def test_optional_variables_take_their_documented_defaults(required_env):
    s = load_settings(env_file=None)
    assert s.jwt_expire_days == 7
    assert s.db_pool_size == 5
    assert s.db_max_overflow == 10
    assert s.db_pool_timeout == 30
    assert s.cors_origins == ["http://localhost:3000"]
    assert s.fitman_log_format == "json"
    assert s.rate_limit_disabled is False
    assert s.scale_height_cm == 0
    assert s.scale_age == 0
    assert s.scale_sex == 1


def test_secret_key_is_typed_str(required_env):
    """The #222 property, kept: PyJWT is never handed None."""
    assert load_settings(env_file=None).secret_key == "test-secret"


# ── Parsing ───────────────────────────────────────────────────────────────────


def test_cors_origins_are_split_on_commas_and_trimmed(required_env):
    required_env.setenv("CORS_ORIGINS", "http://a.example, http://b.example")
    assert load_settings(env_file=None).cors_origins == [
        "http://a.example",
        "http://b.example",
    ]


@pytest.mark.parametrize("raw", ["true", "TRUE", "1"])
def test_rate_limit_disabled_accepts_true_values(required_env, raw):
    required_env.setenv("RATE_LIMIT_DISABLED", raw)
    assert load_settings(env_file=None).rate_limit_disabled is True


def test_numeric_variables_are_parsed(required_env):
    required_env.setenv("DB_POOL_SIZE", "3")
    required_env.setenv("SCALE_HEIGHT_CM", "181.5")
    s = load_settings(env_file=None)
    assert s.db_pool_size == 3
    assert s.scale_height_cm == 181.5


# ── Every problem, reported together ─────────────────────────────────────────


def test_all_problems_are_reported_in_one_message(clean_env):
    """A bad deploy used to fail on the first problem, once per restart."""
    clean_env.setenv("DB_POOL_SIZE", "abc")
    clean_env.setenv("JWT_EXPIRE_DAYS", "soon")
    message = _problems()
    for name in ("SECRET_KEY", "DATABASE_URL", "DB_POOL_SIZE", "JWT_EXPIRE_DAYS"):
        assert name in message, f"{name} missing from:\n{message}"
    assert "'abc'" in message
    assert "'soon'" in message


def test_message_names_variables_not_pydantic_internals(clean_env):
    message = _problems()
    assert "secret_key" not in message, "field name leaked; operators set SECRET_KEY"
    assert "errors.pydantic.dev" not in message
    assert "ValidationError" not in message


def test_message_points_at_the_example_file(clean_env):
    assert ".env.example" in _problems()


def test_empty_secret_key_counts_as_missing(required_env):
    """main.py's check treated SECRET_KEY= as missing; that must not regress."""
    required_env.setenv("SECRET_KEY", "")
    assert "SECRET_KEY" in _problems()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FITMAN_LOG_FORMAT", "jsno"),  # was silently treated as json
        ("RATE_LIMIT_DISABLED", "ture"),  # was silently left enabled
        ("SCALE_SEX", "2"),  # formulas accept 0 (female) or 1 (male)
        ("DB_POOL_SIZE", "0"),
        ("DB_POOL_TIMEOUT", "0"),
        ("DB_MAX_OVERFLOW", "-1"),
        ("JWT_EXPIRE_DAYS", "0"),
        ("SCALE_AGE", "-5"),
        ("SCALE_HEIGHT_CM", "-180"),
    ],
)
def test_out_of_range_values_are_rejected_by_name(required_env, name, value):
    required_env.setenv(name, value)
    message = _problems()
    assert name in message
    assert repr(value) in message


# ── The .env file ─────────────────────────────────────────────────────────────


def test_default_env_file_is_the_repo_root(clean_env):
    """`fastapi dev` from backend/ found the root .env via find_dotenv; keep that."""
    assert ENV_FILE == REPO_ROOT / ".env"


def test_env_file_values_are_read(clean_env, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECRET_KEY=from-file\n"
        "DATABASE_URL=postgresql://x@localhost/fitman_test\n"
        "JWT_EXPIRE_DAYS=14\n"
    )
    s = load_settings(env_file=env_file)
    assert s.secret_key == "from-file"
    assert s.jwt_expire_days == 14


def test_env_file_keys_for_other_tools_are_ignored(clean_env, tmp_path):
    """Existing .env files carry keys the backend doesn't read (ADMIN_USERNAME etc.,
    from the retired scale_ingest.py).

    pydantic-settings rejects unknown env-file keys by default, which would
    turn a working .env into a startup failure.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECRET_KEY=from-file\n"
        "DATABASE_URL=postgresql://x@localhost/fitman_test\n"
        "ADMIN_USERNAME=dave\n"
        "ADMIN_PASSWORD=hunter2\n"
    )
    assert load_settings(env_file=env_file).secret_key == "from-file"


def test_environment_overrides_env_file(clean_env, tmp_path):
    """Same precedence as load_dotenv(override=False): compose env wins."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECRET_KEY=from-file\nDATABASE_URL=postgresql://x@localhost/fitman_test\n"
    )
    clean_env.setenv("SECRET_KEY", "from-environment")
    assert load_settings(env_file=env_file).secret_key == "from-environment"


def test_missing_env_file_is_not_an_error(required_env, tmp_path):
    """Containers get their config from compose, with no .env inside the image."""
    assert load_settings(env_file=tmp_path / "absent.env").secret_key == "test-secret"


# ── Startup ───────────────────────────────────────────────────────────────────


def test_bad_config_stops_startup_with_a_readable_message(tmp_path):
    """The operator-facing path: importing the app, not calling load_settings.

    Empty values rather than unset ones, because the repo-root .env would
    otherwise supply them — and an environment variable wins over the file,
    which test_environment_overrides_env_file pins.
    """
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(BACKEND_DIR),
        "SECRET_KEY": "",
        "DATABASE_URL": "",
        "DB_POOL_SIZE": "abc",
    }
    result = subprocess.run(  # noqa: S603 — fixed interpreter and argument
        [sys.executable, "-c", "import main"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    for name in ("SECRET_KEY", "DATABASE_URL", "DB_POOL_SIZE"):
        assert name in combined, f"{name} missing from:\n{combined}"
    assert "Traceback" not in combined, combined


# ── One source of truth ──────────────────────────────────────────────────────


def _application_modules() -> list[Path]:
    """Every backend module that runs in the app or in migrations.

    tests/ set defaults deliberately; scripts/ are standalone dev tools;
    alembic/versions/ are frozen history. Everything else is in scope.
    """
    skip = {"tests", "scripts", ".venv", "venv", "__pycache__"}
    modules = []
    for path in BACKEND_DIR.rglob("*.py"):
        rel = path.relative_to(BACKEND_DIR)
        if rel.parts[0] in skip or rel.parts[:2] == ("alembic", "versions"):
            continue
        modules.append(path)
    return modules


def test_the_module_scan_actually_finds_the_modules():
    """Guard against the scan below passing because it read nothing."""
    names = {p.relative_to(BACKEND_DIR).as_posix() for p in _application_modules()}
    for expected in (
        "main.py",
        "auth.py",
        "database.py",
        "limiter.py",
        "config.py",
        "routers/measurements.py",
        "alembic/env.py",
    ):
        assert expected in names


def _environment_reads(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in {"getenv", "environ"}
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
        ):
            found.append(f"os.{node.attr} at line {node.lineno}")
        if isinstance(node, ast.ImportFrom) and node.module in {"os", "dotenv"}:
            for alias in node.names:
                if alias.name in {"getenv", "environ", "load_dotenv", "find_dotenv"}:
                    found.append(f"from {node.module} import {alias.name}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dotenv":
                    found.append("import dotenv")
    return found


def test_only_config_reads_the_environment():
    offenders = {
        path.relative_to(BACKEND_DIR).as_posix(): reads
        for path in _application_modules()
        if path.name != "config.py" or path.parent != BACKEND_DIR
        if (reads := _environment_reads(path))
    }
    assert offenders == {}, (
        "read configuration through config.settings, not the environment:\n"
        + "\n".join(f"  {p}: {', '.join(r)}" for p, r in offenders.items())
    )


def test_every_setting_is_documented_in_env_example():
    example = (REPO_ROOT / ".env.example").read_text()
    undocumented = [
        name.upper()
        for name in Settings.model_fields
        if f"{name.upper()}=" not in example
    ]
    assert undocumented == []


def test_settings_cover_exactly_the_known_variables():
    """Adding a variable means adding it here, to FITMAN_VARS and the fixture."""
    assert sorted(n.upper() for n in Settings.model_fields) == sorted(FITMAN_VARS)
