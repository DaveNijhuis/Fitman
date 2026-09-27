from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.exercise import Exercise
from models.template import SessionTemplate
from models.user import User
from session_templates import template_exercises, visible_templates

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    muscles: str | None
    type: str
    equip: str


# Session names in place of templates: what the frontend uses until #355
# moves it to /api/templates, which removes these.


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[str]:
    return [t.name for t in visible_templates(db, current_user)]


@router.get("")
def list_exercises(
    session: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExerciseOut]:
    if session is not None:
        template = (
            visible_templates(db, current_user)
            .filter(SessionTemplate.name == session)
            .first()
        )
        if not template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown session"
            )
        exercises = template_exercises(db, template)
        if search is not None:
            exercises = [e for e in exercises if search.lower() in e.name.lower()]
        return [ExerciseOut.model_validate(e) for e in exercises]

    query = db.query(Exercise)
    if search is not None:
        query = query.filter(Exercise.name.ilike(f"%{search}%"))
    return [ExerciseOut.model_validate(e) for e in query.order_by(Exercise.id).all()]


@router.get("/{exercise_id}")
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> ExerciseOut:
    exercise = db.get(Exercise, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )
    return ExerciseOut.model_validate(exercise)
