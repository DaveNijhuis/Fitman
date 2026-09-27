from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from exercise_access import library, visible_exercise
from models.exercise import Exercise
from models.template import SessionTemplate, TemplateExercise
from models.user import User
from models.workout import Log
from session_templates import template_exercises, visible_templates

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    muscles: str | None
    type: str
    equip: str
    custom: bool
    archived: bool


def _required(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be blank")
    return value


def _optional(value: str | None) -> str | None:
    """Whitespace tidied; blank means none."""
    if value is None:
        return None
    return " ".join(value.split()) or None


class ExerciseIn(BaseModel):
    name: str
    muscles: str | None = None
    type: Literal["weight", "bodyweight"]
    # Free text: dumbbell, cable, machine, band — whatever the user has (#358).
    equip: str

    _name = field_validator("name", "equip")(_required)
    _muscles = field_validator("muscles")(_optional)


class ExerciseUpdate(BaseModel):
    name: str | None = None
    muscles: str | None = None
    type: Literal["weight", "bodyweight"] | None = None
    equip: str | None = None

    @field_validator("name", "equip")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        return None if value is None else _required(value)

    _muscles = field_validator("muscles")(_optional)


def _known_spelling(db: Session, user: User, equip: str) -> str:
    """Equipment already in the library, spelled as it is there, or as given.

    "dumbbell" is the Dumbbell filter, not a second one beside it.
    """
    existing = (
        library(db, user)
        .filter(func.lower(Exercise.equip) == equip.lower())
        .with_entities(Exercise.equip)
        .first()
    )
    return existing[0] if existing else equip


def _refuse_taken_name(
    db: Session, user: User, name: str, except_id: int | None = None
) -> None:
    taken = library(db, user).filter(func.lower(Exercise.name) == name.lower())
    if except_id is not None:
        taken = taken.filter(Exercise.id != except_id)
    if taken.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An exercise with that name already exists",
        )


def _own_exercise(db: Session, user: User, exercise_id: int) -> Exercise:
    """The user's own exercise: 404 if they can't see it, 403 for a built-in."""
    exercise = visible_exercise(db, user, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )
    if exercise.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Built-in exercises can't be changed",
        )
    return exercise


@router.get("")
def list_exercises(
    template_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    equip: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ExerciseOut]:
    if template_id is not None:
        template = (
            visible_templates(db, current_user)
            .filter(SessionTemplate.id == template_id)
            .first()
        )
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            )
        exercises = template_exercises(db, template)
        if search is not None:
            exercises = [e for e in exercises if search.lower() in e.name.lower()]
        if equip is not None:
            exercises = [e for e in exercises if e.equip.lower() == equip.lower()]
        return [ExerciseOut.model_validate(e) for e in exercises]

    query = library(db, current_user)
    if search is not None:
        query = query.filter(Exercise.name.ilike(f"%{search}%"))
    if equip is not None:
        query = query.filter(func.lower(Exercise.equip) == equip.lower())
    return [ExerciseOut.model_validate(e) for e in query.order_by(Exercise.id).all()]


@router.get("/equipment")
def list_equipment(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[str]:
    """The equipment in the user's library: suggestions and the filter (#358)."""
    values = {e for (e,) in library(db, current_user).with_entities(Exercise.equip)}
    return sorted(values, key=str.lower)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_exercise(
    body: ExerciseIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseOut:
    _refuse_taken_name(db, current_user, body.name)
    exercise = Exercise(
        user_id=current_user.id,
        name=body.name,
        muscles=body.muscles,
        type=body.type,
        equip=_known_spelling(db, current_user, body.equip),
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.get("/{exercise_id}")
def get_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseOut:
    exercise = visible_exercise(db, current_user, exercise_id)
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found"
        )
    return ExerciseOut.model_validate(exercise)


@router.patch("/{exercise_id}")
def update_exercise(
    exercise_id: int,
    body: ExerciseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ExerciseOut:
    exercise = _own_exercise(db, current_user, exercise_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        _refuse_taken_name(db, current_user, changes["name"], except_id=exercise.id)
    if changes.get("equip") is not None:
        changes["equip"] = _known_spelling(db, current_user, changes["equip"])
    for field in ("name", "type", "equip"):
        if changes.get(field) is not None:
            setattr(exercise, field, changes[field])
    if "muscles" in changes:
        exercise.muscles = changes["muscles"]
    db.commit()
    db.refresh(exercise)
    return ExerciseOut.model_validate(exercise)


@router.delete("/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise(
    exercise_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete it, or archive it if it has history: sets or a place in a template."""
    exercise = _own_exercise(db, current_user, exercise_id)
    in_use = (
        db.query(Log.id).filter(Log.exercise_id == exercise.id).first()
        or db.query(TemplateExercise.id)
        .filter(TemplateExercise.exercise_id == exercise.id)
        .first()
    )
    if in_use:
        exercise.archived_at = datetime.now(timezone.utc)
    else:
        db.delete(exercise)
    db.commit()
