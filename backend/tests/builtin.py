"""Built-in templates by name, for tests that need a workout or an exercise.

Starting a workout takes a template id and the exercise list is per template
(#355); ids depend on insert order, so tests look them up by name.
"""

from typing import Any

from database import SessionLocal
from models.template import SessionTemplate
from routers.exercises import ExerciseOut
from session_templates import template_exercises


def _builtin(db: Any, name: str) -> SessionTemplate:
    return (
        db.query(SessionTemplate)
        .filter(SessionTemplate.user_id.is_(None), SessionTemplate.name == name)
        .one()
    )


def builtin_id(name: str) -> int:
    db = SessionLocal()
    try:
        return _builtin(db, name).id
    finally:
        db.close()


def builtin_exercises(name: str) -> list[dict[str, Any]]:
    """The template's exercises in order, shaped like the API returns them."""
    db = SessionLocal()
    try:
        return [
            ExerciseOut.model_validate(e).model_dump()
            for e in template_exercises(db, _builtin(db, name))
        ]
    finally:
        db.close()
