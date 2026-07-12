import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.user import User
from models.workout import Log, WorkoutSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _iso_week_bounds() -> tuple[str, str]:
    today = _today_utc()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _compute_streak(trained_dates: set[str]) -> int:
    if not trained_dates:
        return 0
    today = _today_utc()
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
    current_user: User = Depends(get_current_user),
):
    week_start, week_end = _iso_week_bounds()
    week_start_dt = datetime.fromisoformat(week_start).replace(tzinfo=timezone.utc)
    week_end_dt = datetime.fromisoformat(week_end).replace(
        tzinfo=timezone.utc
    ) + timedelta(days=1)

    prev_start_dt = week_start_dt - timedelta(weeks=1)
    prev_end_dt = week_end_dt - timedelta(weeks=1)

    # Streak — date-only query bounded to 365 days (covers any realistic streak)
    streak_cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    trained_dates = {
        row[0].isoformat()
        for row in db.query(cast(WorkoutSession.started_at, Date))
        .filter(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.started_at >= streak_cutoff,
        )
        .all()
    }
    streak = _compute_streak(trained_dates)

    # Current week — single aggregated query
    week_row = (
        db.query(
            func.count(WorkoutSession.id.distinct()).label("workouts"),
            func.coalesce(func.sum(Log.weight * Log.reps), 0).label("volume"),
            func.coalesce(
                func.sum(
                    func.extract(
                        "epoch", WorkoutSession.ended_at - WorkoutSession.started_at
                    )
                    / 60
                ),
                0,
            ).label("minutes"),
        )
        .select_from(WorkoutSession)
        .outerjoin(Log, Log.session_id == WorkoutSession.id)
        .filter(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.started_at >= week_start_dt,
            WorkoutSession.started_at < week_end_dt,
        )
        .one()
    )
    week_workouts = week_row.workouts
    week_volume = round(float(week_row.volume), 1)
    week_minutes = int(week_row.minutes)

    # Previous week volume — single aggregated query
    prev_row = (
        db.query(
            func.coalesce(func.sum(Log.weight * Log.reps), 0).label("volume"),
        )
        .select_from(WorkoutSession)
        .outerjoin(Log, Log.session_id == WorkoutSession.id)
        .filter(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.ended_at.isnot(None),
            WorkoutSession.started_at >= prev_start_dt,
            WorkoutSession.started_at < prev_end_dt,
        )
        .one()
    )
    prev_week_volume = round(float(prev_row.volume), 1)

    return HomeStats(
        streak=streak,
        week_workouts=week_workouts,
        week_volume=week_volume,
        week_minutes=week_minutes,
        prev_week_volume=prev_week_volume,
    )
