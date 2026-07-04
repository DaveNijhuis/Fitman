from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.exercise import Exercise

router = APIRouter(prefix="/api/exercises", tags=["exercises"])

SESSIONS = ["Push A", "Pull A", "Legs A"]


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    muscles: str | None
    session: str
    position: int
    type: str
    equip: str


@router.get("/sessions")
def list_sessions(_: str = Depends(get_current_user)) -> list[str]:
    return SESSIONS


@router.get("")
def list_exercises(
    session: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> list[ExerciseOut]:
    if session is not None and session not in SESSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown session"
        )

    query = db.query(Exercise)
    if session is not None:
        query = query.filter(Exercise.session == session)
    if search is not None:
        query = query.filter(Exercise.name.ilike(f"%{search}%"))

    return [
        ExerciseOut.model_validate(e)
        for e in query.order_by(Exercise.session, Exercise.position).all()
    ]


@router.get("/{exercise_id}")
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
) -> ExerciseOut:
    exercise = db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )
    return ExerciseOut.model_validate(exercise)
