import os
from collections.abc import Iterator
from datetime import datetime, timezone
from urllib.parse import urlsplit

import bcrypt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-ci-only-not-for-production-use"
)
os.environ.setdefault(
    "DATABASE_URL", "postgresql://fitman:fitman@localhost:5432/fitman_test"
)


def _require_test_database(url: str) -> None:
    """Refuse to run against anything but a database named for testing (#248).

    The next two lines drop every application table. DATABASE_URL is read with
    setdefault, so the safe default applies only when the variable is unset —
    and the README development instructions tell you to export it for
    `alembic upgrade head` and `fastapi dev`. Running pytest in that shell
    destroyed the working database with no warning.
    """
    name = urlsplit(url).path.lstrip("/")
    if not name.endswith("_test"):
        raise pytest.UsageError(
            f"Refusing to run: DATABASE_URL points at {name!r}, which is not a "
            "test database. The suite drops every table before it starts, so "
            "it only runs against a database whose name ends in '_test'. "
            "Unset DATABASE_URL to use the default, or point it at "
            f"'{name}_test'."
        )


from database import Base, SessionLocal, engine  # noqa: E402
from limiter import limiter  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402


@pytest.fixture(scope="session")
def database() -> Iterator[None]:
    """Build the schema and seed it, once per session (#283).

    Requested rather than done at import, so collection opens no connection
    and the config-only test modules — which read YAML, .gitignore and compose
    files — run with no database at all.

    The guard moved here with the destructive calls it protects. It still fires
    before anything is dropped, which is the actual protection; running it at
    import would also refuse a config-only run that never touches the database.
    """
    _require_test_database(os.environ["DATABASE_URL"])

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    db.add(
        User(
            username="testuser",
            hashed_password=bcrypt.hashpw(
                b"testpass", bcrypt.gensalt(rounds=4)
            ).decode(),
            is_active=True,
            is_admin=True,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()

    yield


@pytest.fixture(autouse=True)
def reset_rate_limits():
    limiter.reset()


@pytest.fixture(scope="session")
def client(database: None) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
