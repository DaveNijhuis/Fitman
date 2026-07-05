"""Connection pool configuration tests (#134).

Tests call _make_engine() directly with monkeypatched env vars so the
module-level singleton engine is never touched.  Uses DATABASE_URL from
the environment (PostgreSQL) — pool_size args don't apply to SQLite's
StaticPool so a real PostgreSQL URL is required.
"""

import os


def _url() -> str:
    return os.environ["DATABASE_URL"]


def test_pool_size_defaults_to_five(monkeypatch):
    """Without DB_POOL_SIZE the pool must default to 5."""
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    from database import _make_engine

    e = _make_engine(_url())
    try:
        assert e.pool.size() == 5
    finally:
        e.dispose()


def test_pool_size_is_configurable(monkeypatch):
    """DB_POOL_SIZE env var must set the pool size."""
    monkeypatch.setenv("DB_POOL_SIZE", "3")
    from database import _make_engine

    e = _make_engine(_url())
    try:
        assert e.pool.size() == 3
    finally:
        e.dispose()


def test_max_overflow_defaults_to_ten(monkeypatch):
    """Without DB_MAX_OVERFLOW the pool must default to 10."""
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    from database import _make_engine

    e = _make_engine(_url())
    try:
        assert e.pool._max_overflow == 10
    finally:
        e.dispose()


def test_max_overflow_is_configurable(monkeypatch):
    """DB_MAX_OVERFLOW env var must set the pool max overflow."""
    monkeypatch.setenv("DB_MAX_OVERFLOW", "2")
    from database import _make_engine

    e = _make_engine(_url())
    try:
        assert e.pool._max_overflow == 2
    finally:
        e.dispose()


def test_pool_timeout_defaults_to_thirty(monkeypatch):
    """Without DB_POOL_TIMEOUT the pool timeout must default to 30 seconds."""
    monkeypatch.delenv("DB_POOL_TIMEOUT", raising=False)
    from database import _make_engine

    e = _make_engine(_url())
    try:
        assert e.pool._timeout == 30
    finally:
        e.dispose()


def test_pool_timeout_is_configurable(monkeypatch):
    """DB_POOL_TIMEOUT env var must set the pool timeout in seconds."""
    monkeypatch.setenv("DB_POOL_TIMEOUT", "15")
    from database import _make_engine

    e = _make_engine(_url())
    try:
        assert e.pool._timeout == 15
    finally:
        e.dispose()
