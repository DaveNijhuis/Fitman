from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.exercise import Exercise
from models.user import User
from models.workout import Log, WorkoutSession

router = APIRouter(prefix="/api/progress", tags=["progress"])


def epley_1rm(weight: float, reps: int) -> float:
    if reps == 1:
        return weight
    return weight * (1 + reps / 30)


def _user_logs(db: Session, user_id: int):
    return (
        db.query(Log)
        .join(WorkoutSession, Log.session_id == WorkoutSession.id)
        .filter(WorkoutSession.user_id == user_id)
    )


# ── Strength ──────────────────────────────────────────────────────────────────


class StrengthPoint(BaseModel):
    date: str
    estimated_1rm: float


class StrengthData(BaseModel):
    exercise_id: int
    exercise_name: str
    data: list[StrengthPoint]


@router.get("/strength", response_model=StrengthData)
def strength_progression(
    exercise_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exercise = db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )

    logs = (
        _user_logs(db, current_user.id)
        .filter(Log.exercise_id == exercise_id)
        .order_by(Log.logged_at)
        .all()
    )

    daily_best: dict[str, float] = defaultdict(float)
    for log in logs:
        date = log.logged_at.date().isoformat()
        daily_best[date] = max(daily_best[date], epley_1rm(log.weight, log.reps))

    data = [
        StrengthPoint(date=d, estimated_1rm=round(v, 2))
        for d, v in sorted(daily_best.items())
    ]
    return StrengthData(exercise_id=exercise_id, exercise_name=exercise.name, data=data)


# ── Volume ────────────────────────────────────────────────────────────────────


class VolumePoint(BaseModel):
    week: str
    volume_kg: float


@router.get("/volume", response_model=list[VolumePoint])
def volume_over_time(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs = _user_logs(db, current_user.id).order_by(Log.logged_at).all()
    weekly: dict[str, float] = defaultdict(float)
    for log in logs:
        week = log.logged_at.strftime("%Y-W%V")
        weekly[week] += log.weight * log.reps
    return [
        VolumePoint(week=w, volume_kg=round(v, 2)) for w, v in sorted(weekly.items())
    ]


# ── Consistency ───────────────────────────────────────────────────────────────


class ConsistencyDay(BaseModel):
    date: str
    trained: bool
    session: str | None = None
    volume_kg: float | None = None


class ConsistencyWeek(BaseModel):
    week: str
    days: list[ConsistencyDay]


@router.get("/consistency", response_model=list[ConsistencyWeek])
def consistency(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cutoff = datetime.now(timezone.utc) - timedelta(weeks=17)
    sessions = (
        db.query(WorkoutSession)
        .filter(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.started_at >= cutoff,
            WorkoutSession.ended_at.isnot(None),
        )
        .all()
    )

    trained_data: dict[str, dict] = {}
    for s in sessions:
        date = s.started_at.date().isoformat()
        logs = db.query(Log).filter(Log.session_id == s.id).all()
        volume = sum(log.weight * log.reps for log in logs)
        trained_data[date] = {"session": s.session, "volume_kg": round(volume, 1)}

    now = datetime.now(timezone.utc)
    weeks = []
    for i in range(16, -1, -1):
        week_start = now - timedelta(weeks=i)
        week_start = week_start - timedelta(days=week_start.weekday())
        days = []
        for d in range(7):
            date_str = (week_start + timedelta(days=d)).strftime("%Y-%m-%d")
            if date_str in trained_data:
                days.append(
                    ConsistencyDay(
                        date=date_str,
                        trained=True,
                        session=trained_data[date_str]["session"],
                        volume_kg=trained_data[date_str]["volume_kg"],
                    )
                )
            else:
                days.append(ConsistencyDay(date=date_str, trained=False))
        weeks.append(ConsistencyWeek(week=week_start.strftime("%Y-W%V"), days=days))
    return weeks


# ── Balance ───────────────────────────────────────────────────────────────────


class MuscleBalance(BaseModel):
    muscle: str
    percentage: float


@router.get("/balance", response_model=list[MuscleBalance])
def muscle_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Log, Exercise)
        .join(Exercise, Log.exercise_id == Exercise.id)
        .join(WorkoutSession, Log.session_id == WorkoutSession.id)
        .filter(WorkoutSession.user_id == current_user.id)
        .all()
    )
    muscle_volume: dict[str, float] = defaultdict(float)
    total = 0.0
    for log, exercise in rows:
        if not exercise.muscles:
            continue
        vol = log.weight * log.reps
        muscles = [m.strip() for m in exercise.muscles.split(",") if m.strip()]
        if not muscles:
            continue
        per_muscle = vol / len(muscles)
        for muscle in muscles:
            muscle_volume[muscle] += per_muscle
        total += vol

    if total == 0:
        return []

    return sorted(
        [
            MuscleBalance(muscle=m, percentage=round(v / total * 100, 1))
            for m, v in muscle_volume.items()
        ],
        key=lambda x: -x.percentage,
    )


# ── Personal Records ──────────────────────────────────────────────────────────


class PersonalRecord(BaseModel):
    exercise_id: int
    exercise_name: str
    weight: float
    reps: int
    estimated_1rm: float
    date: str


@router.get("/prs", response_model=list[PersonalRecord])
def personal_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exercises = db.query(Exercise).order_by(Exercise.name).all()
    prs = []
    for exercise in exercises:
        logs = (
            _user_logs(db, current_user.id).filter(Log.exercise_id == exercise.id).all()
        )
        if not logs:
            continue
        best = max(logs, key=lambda log: epley_1rm(log.weight, log.reps))
        prs.append(
            PersonalRecord(
                exercise_id=exercise.id,
                exercise_name=exercise.name,
                weight=best.weight,
                reps=best.reps,
                estimated_1rm=round(epley_1rm(best.weight, best.reps), 2),
                date=best.logged_at.date().isoformat(),
            )
        )
    return prs
