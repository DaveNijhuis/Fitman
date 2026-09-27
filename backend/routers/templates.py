import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from exercise_access import library
from models.exercise import Exercise
from models.template import HiddenTemplate, SessionTemplate, TemplateExercise
from models.user import User
from routers.exercises import ExerciseOut
from session_templates import template_exercises, visible_templates

router = APIRouter(prefix="/api/templates", tags=["templates"])

_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    focus: str | None
    colour: str | None
    builtin: bool
    # A built-in the user has hidden from Home and the picker (#359).
    hidden: bool


class TemplateDetail(TemplateOut):
    exercises: list[ExerciseOut]


def _tidy(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.split()) or None


def _check_colour(value: str | None) -> str | None:
    if value is not None and not _COLOUR.match(value):
        raise ValueError("must be a colour like #ff5a36")
    return value.lower() if value else value


def _check_exercises(value: list[int] | None) -> list[int] | None:
    if value is not None:
        if not value:
            raise ValueError("a day needs at least one exercise")
        if len(set(value)) != len(value):
            raise ValueError("an exercise can appear once in a day")
    return value


class TemplateIn(BaseModel):
    name: str
    focus: str | None = None
    colour: str | None = None
    exercise_ids: list[int]

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        tidy = _tidy(value)
        if not tidy:
            raise ValueError("must not be blank")
        return tidy

    _focus = field_validator("focus")(_tidy)
    _colour = field_validator("colour")(_check_colour)
    _exercises = field_validator("exercise_ids")(_check_exercises)


class TemplateUpdate(BaseModel):
    name: str | None = None
    focus: str | None = None
    colour: str | None = None
    exercise_ids: list[int] | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        tidy = _tidy(value)
        if not tidy:
            raise ValueError("must not be blank")
        return tidy

    _focus = field_validator("focus")(_tidy)
    _colour = field_validator("colour")(_check_colour)
    _exercises = field_validator("exercise_ids")(_check_exercises)


class HiddenIn(BaseModel):
    hidden: bool


def _hidden_ids(db: Session, user: User) -> set[int]:
    return {
        t
        for (t,) in db.query(HiddenTemplate.template_id).filter(
            HiddenTemplate.user_id == user.id
        )
    }


def _out(template: SessionTemplate, hidden: set[int]) -> TemplateOut:
    return TemplateOut(
        id=template.id,
        name=template.name,
        focus=template.focus,
        colour=template.colour,
        builtin=template.user_id is None,
        hidden=template.id in hidden,
    )


def _detail(db: Session, user: User, template: SessionTemplate) -> TemplateDetail:
    return TemplateDetail(
        **_out(template, _hidden_ids(db, user)).model_dump(),
        exercises=[
            ExerciseOut.model_validate(e) for e in template_exercises(db, template)
        ],
    )


def _visible(db: Session, user: User, template_id: int) -> SessionTemplate:
    template = (
        visible_templates(db, user).filter(SessionTemplate.id == template_id).first()
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return template


def _own(db: Session, user: User, template_id: int) -> SessionTemplate:
    """The user's own day: 404 if they can't see it, 403 for a built-in."""
    template = _visible(db, user, template_id)
    if template.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Built-in days can't be changed; duplicate one instead",
        )
    return template


def _name_taken(
    db: Session, user: User, name: str, except_id: int | None = None
) -> bool:
    taken = visible_templates(db, user).filter(
        func.lower(SessionTemplate.name) == name.lower()
    )
    if except_id is not None:
        taken = taken.filter(SessionTemplate.id != except_id)
    return taken.first() is not None


def _refuse_taken_name(
    db: Session, user: User, name: str, except_id: int | None = None
) -> None:
    if _name_taken(db, user, name, except_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a day with that name",
        )


def _refuse_unknown_exercises(db: Session, user: User, ids: list[int]) -> None:
    """Only the user's library: built-ins and their own, none archived."""
    found = {
        i
        for (i,) in library(db, user)
        .filter(Exercise.id.in_(ids))
        .with_entities(Exercise.id)
    }
    if found != set(ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Every exercise must be in your library",
        )


def _set_exercises(db: Session, template: SessionTemplate, ids: list[int]) -> None:
    db.query(TemplateExercise).filter(
        TemplateExercise.template_id == template.id
    ).delete()
    db.flush()
    db.add_all(
        TemplateExercise(template_id=template.id, exercise_id=e, position=i)
        for i, e in enumerate(ids)
    )


def _next_position(db: Session, user: User) -> int:
    last = (
        db.query(func.max(SessionTemplate.position))
        .filter(SessionTemplate.user_id == user.id)
        .scalar()
    )
    return 0 if last is None else last + 1


@router.get("")
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TemplateOut]:
    hidden = _hidden_ids(db, current_user)
    return [_out(t, hidden) for t in visible_templates(db, current_user)]


@router.get("/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateDetail:
    return _detail(db, current_user, _visible(db, current_user, template_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_template(
    body: TemplateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateDetail:
    _refuse_taken_name(db, current_user, body.name)
    _refuse_unknown_exercises(db, current_user, body.exercise_ids)
    template = SessionTemplate(
        user_id=current_user.id,
        name=body.name,
        focus=body.focus,
        colour=body.colour,
        position=_next_position(db, current_user),
    )
    db.add(template)
    db.flush()
    _set_exercises(db, template, body.exercise_ids)
    db.commit()
    return _detail(db, current_user, template)


@router.patch("/{template_id}")
def update_template(
    template_id: int,
    body: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateDetail:
    template = _own(db, current_user, template_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name") is not None:
        _refuse_taken_name(db, current_user, changes["name"], except_id=template.id)
        template.name = changes["name"]
    if "focus" in changes:
        template.focus = changes["focus"]
    if "colour" in changes:
        template.colour = changes["colour"]
    if changes.get("exercise_ids") is not None:
        _refuse_unknown_exercises(db, current_user, changes["exercise_ids"])
        _set_exercises(db, template, changes["exercise_ids"])
    db.commit()
    return _detail(db, current_user, template)


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Its workouts keep their name and their own exercise list (#359)."""
    db.delete(_own(db, current_user, template_id))
    db.commit()


@router.post("/{template_id}/duplicate", status_code=status.HTTP_201_CREATED)
def duplicate_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateDetail:
    """An editable copy of any day the user can see, built-in or their own."""
    source = _visible(db, current_user, template_id)
    name, n = f"{source.name} (copy)", 1
    while _name_taken(db, current_user, name):
        n += 1
        name = f"{source.name} (copy {n})"
    copy = SessionTemplate(
        user_id=current_user.id,
        name=name,
        focus=source.focus,
        colour=source.colour,
        position=_next_position(db, current_user),
    )
    db.add(copy)
    db.flush()
    _set_exercises(db, copy, [e.id for e in template_exercises(db, source)])
    db.commit()
    return _detail(db, current_user, copy)


@router.put("/{template_id}/hidden")
def set_hidden(
    template_id: int,
    body: HiddenIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateOut:
    """Hide a built-in from Home and the picker; still startable (#359)."""
    template = _visible(db, current_user, template_id)
    if template.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only built-in days can be hidden; delete your own instead",
        )
    existing = db.get(HiddenTemplate, (current_user.id, template.id))
    if body.hidden and not existing:
        db.add(HiddenTemplate(user_id=current_user.id, template_id=template.id))
    elif not body.hidden and existing:
        db.delete(existing)
    db.commit()
    return _out(template, _hidden_ids(db, current_user))
