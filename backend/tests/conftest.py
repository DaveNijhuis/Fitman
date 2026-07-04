import os
from datetime import datetime, timezone

import bcrypt
import pytest
from fastapi.testclient import TestClient

# Must be set before the app is imported so main.py startup checks pass
os.environ.setdefault("SECRET_KEY", "test-secret-key-ci-only")
os.environ.setdefault("DATA_DIR", "/tmp/fitman_test")

from database import Base, SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models.user import User  # noqa: E402

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)

# Seed a test user directly in the DB
_db = SessionLocal()
_db.add(User(
    username="testuser",
    hashed_password=bcrypt.hashpw(b"testpass", bcrypt.gensalt(rounds=4)).decode(),
    is_active=True,
    is_admin=True,
    created_at=datetime.now(timezone.utc),
))
_db.commit()
_db.close()


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
