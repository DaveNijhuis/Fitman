"""FK constraint + ON DELETE CASCADE tests (#184).

The test DB is built via Base.metadata.create_all so FK declarations on the
models are what drive these tests. The Alembic migration must also be updated
for production, but correctness is proved here at the model level.
"""

from datetime import datetime, timezone

import bcrypt
from sqlalchemy import inspect, text

from database import SessionLocal, engine
from models.cardio import CardioEntry
from models.measurement import BodyMeasurement
from models.user import User
from models.workout import WorkoutSession


def _user_id_fk(table: str) -> dict | None:
    for fk in inspect(engine).get_foreign_keys(table):
        if "user_id" in fk["constrained_columns"]:
            return fk
    return None


# ── FK constraint exists ───────────────────────────────────────────────────────


def test_workout_sessions_user_id_fk_exists():
    assert _user_id_fk("workout_sessions") is not None


def test_cardio_entries_user_id_fk_exists():
    assert _user_id_fk("cardio_entries") is not None


def test_body_measurements_user_id_fk_exists():
    assert _user_id_fk("body_measurements") is not None


# ── ON DELETE CASCADE ─────────────────────────────────────────────────────────


def test_workout_sessions_user_id_fk_has_cascade_delete():
    fk = _user_id_fk("workout_sessions")
    assert fk is not None
    assert fk.get("options", {}).get("ondelete", "").upper() == "CASCADE", (
        f"workout_sessions.user_id FK missing ON DELETE CASCADE; options={fk.get('options')}"
    )


def test_cardio_entries_user_id_fk_has_cascade_delete():
    fk = _user_id_fk("cardio_entries")
    assert fk is not None
    assert fk.get("options", {}).get("ondelete", "").upper() == "CASCADE", (
        f"cardio_entries.user_id FK missing ON DELETE CASCADE; options={fk.get('options')}"
    )


def test_body_measurements_user_id_fk_has_cascade_delete():
    fk = _user_id_fk("body_measurements")
    assert fk is not None
    assert fk.get("options", {}).get("ondelete", "").upper() == "CASCADE", (
        f"body_measurements.user_id FK missing ON DELETE CASCADE; options={fk.get('options')}"
    )


# ── Behavioural: raw delete cascades to child rows ────────────────────────────


def _make_user_with_data() -> int:
    db = SessionLocal()
    user = User(
        username=f"cascade_test_{datetime.now(timezone.utc).timestamp()}",
        hashed_password=bcrypt.hashpw(b"pass1234", bcrypt.gensalt(rounds=4)).decode(),
        is_active=True,
        is_admin=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    db.add(
        WorkoutSession(
            user_id=user_id,
            session="Push A",
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        CardioEntry(
            user_id=user_id,
            activity="Run",
            duration_s=600,
            logged_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        BodyMeasurement(
            user_id=user_id,
            weight_kg=75.0,
            recorded_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.close()
    return user_id


def test_raw_user_delete_cascades_workout_sessions():
    user_id = _make_user_with_data()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        conn.commit()
    db = SessionLocal()
    count = db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).count()
    db.close()
    assert count == 0, f"Expected 0 workout_sessions after user delete, got {count}"


def test_raw_user_delete_cascades_cardio_entries():
    user_id = _make_user_with_data()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        conn.commit()
    db = SessionLocal()
    count = db.query(CardioEntry).filter(CardioEntry.user_id == user_id).count()
    db.close()
    assert count == 0, f"Expected 0 cardio_entries after user delete, got {count}"


def test_raw_user_delete_cascades_body_measurements():
    user_id = _make_user_with_data()
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        conn.commit()
    db = SessionLocal()
    count = db.query(BodyMeasurement).filter(BodyMeasurement.user_id == user_id).count()
    db.close()
    assert count == 0, f"Expected 0 body_measurements after user delete, got {count}"
