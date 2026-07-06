import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.exercise import Exercise
from models.user import User
from models.workout import Log, WorkoutSession
from routers.exercises import SESSIONS

logger = logging.getLogger(__name__)

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
    current_user: User = Depends(get_current_user),
):
    if body.session not in SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown session"
        )
    workout = WorkoutSession(
        user_id=current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(
            WorkoutSession,
            func.count(Log.id).label("set_count"),
            func.coalesce(func.sum(Log.weight * Log.reps), 0.0).label("volume_kg"),
        )
        .outerjoin(Log, Log.session_id == WorkoutSession.id)
        .filter(
            WorkoutSession.user_id == current_user.id,
            WorkoutSession.ended_at.isnot(None),
        )
        .group_by(WorkoutSession.id)
        .order_by(WorkoutSession.started_at.desc())
        .all()
    )
    return [
        WorkoutSessionSummary(
            id=w.id,
            session=w.session,
            started_at=w.started_at,
            ended_at=w.ended_at,
            set_count=set_count,
            volume_kg=float(volume_kg),
        )
        for w, set_count, volume_kg in rows
    ]


@router.get("/{session_id}/logs", response_model=list[SessionLogEntry])
def get_session_logs(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workout = db.get(WorkoutSession, session_id)
    if not workout or workout.user_id != current_user.id:
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


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workout = db.get(WorkoutSession, session_id)
    if not workout or workout.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    if workout.ended_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Session already ended"
        )
    db.query(Log).filter(Log.session_id == session_id).delete()
    db.delete(workout)
    db.commit()


@router.patch("/{session_id}/end", response_model=WorkoutSessionOut)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workout = db.get(WorkoutSession, session_id)
    if not workout or workout.user_id != current_user.id:
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
