from datetime import date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.workout import Log, WorkoutSession

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _iso_week_bounds() -> tuple[str, str]:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _compute_streak(trained_dates: set[str]) -> int:
    if not trained_dates:
        return 0
    today = date.today()
    dates = sorted({date.fromisoformat(d) for d in trained_dates}, reverse=True)
    if dates[0] < today - timedelta(days=1):
        return 0
    streak = 0
    expected = dates[0]
    for d in dates:
        if d == expected:
            streak += 1
            expected -= timedelta(days=1)
        else:
            break
    return streak


class HomeStats(BaseModel):
    streak: int
    week_workouts: int
    week_volume: float
    week_minutes: int
    prev_week_volume: float


@router.get("/home", response_model=HomeStats)
def home_stats(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    week_start, week_end = _iso_week_bounds()

    prev_start = (date.fromisoformat(week_start) - timedelta(weeks=1)).isoformat()
    prev_end = (date.fromisoformat(week_end) - timedelta(weeks=1)).isoformat()

    # Streak — all completed sessions ever
    all_sessions = (
        db.query(WorkoutSession).filter(WorkoutSession.ended_at.isnot(None)).all()
    )
    trained_dates = {s.started_at.date().isoformat() for s in all_sessions}
    streak = _compute_streak(trained_dates)

    # This week's completed sessions
    week_sessions = [
        s
        for s in all_sessions
        if week_start <= s.started_at.date().isoformat() <= week_end
    ]
    week_workouts = len(week_sessions)

    # This week's volume and duration
    week_session_ids = {s.id for s in week_sessions}
    week_logs = (
        db.query(Log).filter(Log.session_id.in_(week_session_ids)).all()
        if week_session_ids
        else []
    )
    week_volume = round(sum(log.weight * log.reps for log in week_logs), 1)

    week_minutes = 0
    for s in week_sessions:
        if s.ended_at:
            week_minutes += int((s.ended_at - s.started_at).total_seconds() / 60)

    # Previous week volume (for delta)
    prev_sessions = [
        s
        for s in all_sessions
        if prev_start <= s.started_at.date().isoformat() <= prev_end
    ]
    prev_ids = {s.id for s in prev_sessions}
    prev_logs = (
        db.query(Log).filter(Log.session_id.in_(prev_ids)).all() if prev_ids else []
    )
    prev_week_volume = round(sum(log.weight * log.reps for log in prev_logs), 1)

    return HomeStats(
        streak=streak,
        week_workouts=week_workouts,
        week_volume=week_volume,
        week_minutes=week_minutes,
        prev_week_volume=prev_week_volume,
    )
