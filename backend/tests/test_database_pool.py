"""Connection pool configuration tests (#134).

Tests call _make_engine() directly so the module-level singleton engine is
never touched. The environment is parsed through Settings, as at startup, and
the result handed to _make_engine explicitly (#250) — the engine no longer
reads the environment itself, so a monkeypatched variable only takes effect
through a freshly loaded Settings.

Uses DATABASE_URL from the environment (PostgreSQL) — pool_size args don't
apply to SQLite's StaticPool so a real PostgreSQL URL is required.
"""

from typing import cast

import pytest
from sqlalchemy import Engine
from sqlalchemy.pool import QueuePool

from config import load_settings
from database import _make_engine


def _pool(e: Engine) -> QueuePool:
    """size()/_max_overflow/_timeout are QueuePool members, not base Pool ones.

    The docstring above already requires PostgreSQL for these tests, which is
    exactly the condition under which the engine uses a QueuePool.
    """
    return cast(QueuePool, e.pool)


def _engine() -> Engine:
    # env_file=None: the repo-root .env sets these variables too, and would
    # otherwise fill in whatever a test deleted.
    return _make_engine(load_settings(env_file=None))


def test_pool_size_defaults_to_five(monkeypatch: pytest.MonkeyPatch):
    """Without DB_POOL_SIZE the pool must default to 5."""
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    e = _engine()
    try:
        assert _pool(e).size() == 5
    finally:
        e.dispose()


def test_pool_size_is_configurable(monkeypatch: pytest.MonkeyPatch):
    """DB_POOL_SIZE env var must set the pool size."""
    monkeypatch.setenv("DB_POOL_SIZE", "3")
    e = _engine()
    try:
        assert _pool(e).size() == 3
    finally:
        e.dispose()


def test_max_overflow_defaults_to_ten(monkeypatch: pytest.MonkeyPatch):
    """Without DB_MAX_OVERFLOW the pool must default to 10."""
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    e = _engine()
    try:
        assert _pool(e)._max_overflow == 10
    finally:
        e.dispose()


def test_max_overflow_is_configurable(monkeypatch: pytest.MonkeyPatch):
    """DB_MAX_OVERFLOW env var must set the pool max overflow."""
    monkeypatch.setenv("DB_MAX_OVERFLOW", "2")
    e = _engine()
    try:
        assert _pool(e)._max_overflow == 2
    finally:
        e.dispose()


def test_pool_timeout_defaults_to_thirty(monkeypatch: pytest.MonkeyPatch):
    """Without DB_POOL_TIMEOUT the pool timeout must default to 30 seconds."""
    monkeypatch.delenv("DB_POOL_TIMEOUT", raising=False)
    e = _engine()
    try:
        assert _pool(e)._timeout == 30
    finally:
        e.dispose()


def test_pool_timeout_is_configurable(monkeypatch: pytest.MonkeyPatch):
    """DB_POOL_TIMEOUT env var must set the pool timeout in seconds."""
    monkeypatch.setenv("DB_POOL_TIMEOUT", "15")
    e = _engine()
    try:
        assert _pool(e)._timeout == 15
    finally:
        e.dispose()


def test_module_engine_is_built_from_settings():
    """The singleton the app uses must come from the same validated object."""
    import database
    from config import settings

    assert database.engine.url.render_as_string(hide_password=False) == (
        settings.database_url
    )
    assert _pool(database.engine).size() == settings.db_pool_size
