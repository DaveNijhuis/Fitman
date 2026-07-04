from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.exercise import Exercise
from models.workout import Log, WorkoutSession
from routers.exercises import SESSIONS

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class StartSessionRequest(BaseModel):
    session: str


class WorkoutSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session: str
    started_at: datetime
    ended_at: datetime | None


class WorkoutSessionSummary(WorkoutSessionOut):
    set_count: int
    volume_kg: float


class SessionLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    exercise_name: str
    weight: float
    reps: int
    logged_at: datetime


@router.post("", response_model=WorkoutSessionOut, status_code=status.HTTP_201_CREATED)
def start_session(
    body: StartSessionRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if body.session not in SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown session"
        )
    workout = WorkoutSession(
        session=body.session,
        started_at=datetime.now(timezone.utc),
    )
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return workout


@router.get("", response_model=list[WorkoutSessionSummary])
def list_sessions(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    workouts = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.ended_at.isnot(None))
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    result = []
    for w in workouts:
        logs = db.query(Log).filter(Log.session_id == w.id).all()
        result.append(
            WorkoutSessionSummary(
                id=w.id,
                session=w.session,
                started_at=w.started_at,
                ended_at=w.ended_at,
                set_count=len(logs),
                volume_kg=sum(log.weight * log.reps for log in logs),
            )
        )
    return result


@router.get("/{session_id}/logs", response_model=list[SessionLogEntry])
def get_session_logs(
    session_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if not db.get(WorkoutSession, session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    rows = (
        db.query(Log, Exercise)
        .join(Exercise, Log.exercise_id == Exercise.id)
        .filter(Log.session_id == session_id)
        .order_by(Log.logged_at)
        .all()
    )
    return [
        SessionLogEntry(
            id=log.id,
            exercise_id=log.exercise_id,
            exercise_name=exercise.name,
            weight=log.weight,
            reps=log.reps,
            logged_at=log.logged_at,
        )
        for log, exercise in rows
    ]


@router.patch("/{session_id}/end", response_model=WorkoutSessionOut)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    workout = db.get(WorkoutSession, session_id)
    if not workout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if workout.ended_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Session already ended"
        )
    workout.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(workout)
    return workout
