from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.exercise import Exercise
from models.workout import Log, WorkoutSession

router = APIRouter(prefix="/api/logs", tags=["logs"])


class LogRequest(BaseModel):
    exercise_id: int
    session_id: int
    weight: float = Field(ge=0)
    reps: int = Field(gt=0)


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exercise_id: int
    session_id: int
    weight: float
    reps: int
    logged_at: datetime


@router.post("", response_model=LogOut, status_code=status.HTTP_201_CREATED)
def log_set(
    body: LogRequest,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if not db.get(Exercise, body.exercise_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )
    if not db.get(WorkoutSession, body.session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    log = Log(
        exercise_id=body.exercise_id,
        session_id=body.session_id,
        weight=body.weight,
        reps=body.reps,
        logged_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/last/{exercise_id}", response_model=LogOut | None)
def get_last_set(
    exercise_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    return (
        db.query(Log)
        .filter(Log.exercise_id == exercise_id)
        .order_by(Log.logged_at.desc())
        .first()
    )


@router.get("", response_model=list[LogOut])
def get_logs(
    exercise_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    return (
        db.query(Log)
        .filter(Log.exercise_id == exercise_id)
        .order_by(Log.logged_at.desc())
        .limit(limit)
        .all()
    )
