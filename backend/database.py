import os
from datetime import datetime, timezone

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import String, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

load_dotenv(find_dotenv())

DATA_DIR = os.getenv("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/fitman.db"


def _make_engine(url: str):
    return create_engine(
        url,
        connect_args={"check_same_thread": False},
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
        pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
    )


engine = _make_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TZDateTime(TypeDecorator):
    """Stores datetimes as ISO strings, returns timezone-aware UTC datetime objects."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    def process_result_value(self, value: str | None, dialect) -> datetime | None:
        if value is None:
            return None
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
