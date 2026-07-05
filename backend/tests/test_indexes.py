"""Schema index tests (#131).

The test DB is built via Base.metadata.create_all so indexes must be declared
on the models — not only in Alembic — to be picked up here.
"""

from sqlalchemy import inspect

from database import engine


def _indexed_columns(table: str) -> set[str]:
    return {
        col for idx in inspect(engine).get_indexes(table) for col in idx["column_names"]
    }


def test_logs_session_id_is_indexed():
    """logs.session_id — used in every session detail and N+1 scan."""
    assert "session_id" in _indexed_columns("logs")


def test_logs_exercise_id_is_indexed():
    """logs.exercise_id — used in strength progression and personal records."""
    assert "exercise_id" in _indexed_columns("logs")


def test_workout_sessions_user_id_is_indexed():
    """workout_sessions.user_id — used in sessions list and all user-scoped joins."""
    assert "user_id" in _indexed_columns("workout_sessions")


def test_body_measurements_user_id_is_indexed():
    """body_measurements.user_id — used in measurements list."""
    assert "user_id" in _indexed_columns("body_measurements")


def test_cardio_entries_user_id_is_indexed():
    """cardio_entries.user_id — used in cardio list."""
    assert "user_id" in _indexed_columns("cardio_entries")
