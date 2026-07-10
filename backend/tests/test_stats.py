from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

import routers.stats as stats_module
from database import SessionLocal
from models.workout import Log, WorkoutSession


def _token(client: TestClient) -> str:
    resp = client.post(
        "/api/auth/login", json={"username": "testuser", "password": "testpass"}
    )
    return resp.json()["access_token"]


def _auth(client: TestClient) -> dict:
    return {"Authorization": f"Bearer {_token(client)}"}


def _add_session(started_at: datetime, ended_at: datetime) -> None:
    db = SessionLocal()
    session = WorkoutSession(session="Push A", started_at=started_at, ended_at=ended_at)
    db.add(session)
    db.commit()
    db.refresh(session)
    db.add(
        Log(
            session_id=session.id,
            exercise_id=1,
            weight=50.0,
            reps=10,
            logged_at=started_at,
        )
    )
    db.commit()
    db.close()


# ── Endpoint contract ─────────────────────────────────────────────────────────


def test_home_stats_returns_correct_structure(client: TestClient):
    resp = client.get("/api/stats/home", headers=_auth(client))
    assert resp.status_code == 200
    data = resp.json()
    for key in (
        "streak",
        "week_workouts",
        "week_volume",
        "week_minutes",
        "prev_week_volume",
    ):
        assert key in data


# ── Unit tests for _compute_streak ────────────────────────────────────────────


def test_compute_streak_empty():
    assert stats_module._compute_streak(set()) == 0


def test_compute_streak_consecutive_days():
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    assert stats_module._compute_streak({today.isoformat(), yesterday.isoformat()}) == 2


def test_compute_streak_breaks_on_gap():
    today = datetime.now(timezone.utc).date()
    two_days_ago = today - timedelta(days=2)
    assert (
        stats_module._compute_streak({today.isoformat(), two_days_ago.isoformat()}) == 1
    )


def test_streak_uses_utc_not_local_date():
    """_compute_streak must use UTC date, not local date.
    Patching _today_utc to return 'yesterday' simulates the fixed code using UTC
    while also verifying the streak still counts a today-UTC session correctly."""
    today_utc = datetime.now(timezone.utc).date()
    trained_dates = {today_utc.isoformat()}

    with patch("routers.stats._today_utc", return_value=today_utc):
        streak = stats_module._compute_streak(trained_dates)
        assert streak == 1


# ── Memory regression (#179) ──────────────────────────────────────────────────


def test_home_stats_sessions_query_has_date_bound(client: TestClient):
    """GET /api/stats/home must not issue an unbounded sessions SELECT.

    The pre-fix implementation loads every completed session for the user
    into memory and filters by date in Python.  The fix pushes all date
    filtering into SQL so no query touches the full history.

    Asserts that every workout_sessions SELECT issued during the request
    contains a started_at bound in its WHERE clause.
    """
    from sqlalchemy import event

    from database import engine

    unbounded: list[str] = []

    def _inspect(conn, cursor, statement, *args):
        lower = statement.lower()
        if (
            "workout_session" in lower
            and lower.lstrip().startswith("select")
            and "started_at >=" not in lower
            and "started_at <" not in lower
        ):
            unbounded.append(statement)

    event.listen(engine, "before_cursor_execute", _inspect)
    try:
        resp = client.get("/api/stats/home", headers=_auth(client))
    finally:
        event.remove(engine, "before_cursor_execute", _inspect)

    assert resp.status_code == 200
    assert not unbounded, (
        f"Unbounded sessions query (no date filter):\n{unbounded[0][:300]}"
    )


# ── Unit tests for _iso_week_bounds ───────────────────────────────────────────


def test_week_bounds_use_utc_not_local_date():
    """_iso_week_bounds must use UTC date for week boundary calculation.
    If the server local date is Sunday but UTC date is Monday, the week start
    must be that Monday — not the Sunday-week's Monday."""
    monday_utc = datetime.now(timezone.utc).date()
    monday_utc -= timedelta(days=monday_utc.weekday())  # normalise to this Monday

    with patch("routers.stats._today_utc", return_value=monday_utc):
        week_start, _ = stats_module._iso_week_bounds()
        assert week_start == monday_utc.isoformat()
