import os
from datetime import datetime, timezone

import bcrypt
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "SECRET_KEY", "test-secret-key-for-ci-only-not-for-production-use"
)
os.environ.setdefault(
    "DATABASE_URL", "postgresql://fitman:fitman@localhost:5432/fitman_test"
)

from database import Base, SessionLocal, engine  # noqa: E402
from limiter import limiter  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

# Seed a test user directly in the DB
_db = SessionLocal()
_db.add(
    User(
        username="testuser",
        hashed_password=bcrypt.hashpw(b"testpass", bcrypt.gensalt(rounds=4)).decode(),
        is_active=True,
        is_admin=True,
        created_at=datetime.now(timezone.utc),
    )
)
_db.commit()
_db.close()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    limiter.reset()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
