"""PostgreSQL migration structural tests (#132).

These tests verify the engine and models are PostgreSQL-native — no SQLite
custom types, no SQLite-specific connection arguments.
"""

from database import engine


def test_engine_dialect_is_postgresql():
    """The engine must connect to PostgreSQL, not SQLite."""
    assert engine.dialect.name == "postgresql", (
        f"Expected postgresql dialect, got {engine.dialect.name!r}. "
        "Set DATABASE_URL=postgresql://fitman:fitman@localhost:5432/fitman_test"
    )


def test_no_tztime_custom_type_in_user_model():
    """User model must use DateTime(timezone=True), not the custom TZDateTime."""
    from sqlalchemy import DateTime

    from models.user import User

    for col in User.__table__.columns:
        assert not col.type.__class__.__name__ == "TZDateTime", (
            f"Column {col.name!r} still uses TZDateTime — replace with DateTime(timezone=True)"
        )
        if hasattr(col.type, "timezone"):
            assert col.type.timezone is True or not isinstance(col.type, DateTime), (
                f"DateTime column {col.name!r} must have timezone=True"
            )


def test_no_tztime_custom_type_in_workout_models():
    """WorkoutSession and Log must use DateTime(timezone=True), not TZDateTime."""
    from models.workout import Log, WorkoutSession

    for model in (WorkoutSession, Log):
        for col in model.__table__.columns:
            assert col.type.__class__.__name__ != "TZDateTime", (
                f"{model.__name__}.{col.name} still uses TZDateTime"
            )


def test_no_tztime_custom_type_in_cardio_model():
    """CardioEntry must use DateTime(timezone=True), not TZDateTime."""
    from models.cardio import CardioEntry

    for col in CardioEntry.__table__.columns:
        assert col.type.__class__.__name__ != "TZDateTime", (
            f"CardioEntry.{col.name} still uses TZDateTime"
        )


def test_no_tztime_custom_type_in_measurement_model():
    """BodyMeasurement must use DateTime(timezone=True), not TZDateTime."""
    from models.measurement import BodyMeasurement

    for col in BodyMeasurement.__table__.columns:
        assert col.type.__class__.__name__ != "TZDateTime", (
            f"BodyMeasurement.{col.name} still uses TZDateTime"
        )
