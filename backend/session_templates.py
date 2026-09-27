"""Which templates a user may see, and a template's exercises in order (#354)."""

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from models.exercise import Exercise
from models.template import SessionTemplate, TemplateExercise
from models.user import User


def visible_templates(db: Session, user: User) -> Query[SessionTemplate]:
    """Built-ins plus the user's own, built-ins first. Never another user's."""
    return (
        db.query(SessionTemplate)
        .filter(
            or_(SessionTemplate.user_id.is_(None), SessionTemplate.user_id == user.id)
        )
        .order_by(
            SessionTemplate.user_id.is_not(None),
            SessionTemplate.position,
            SessionTemplate.id,
        )
    )


def template_exercises(db: Session, template: SessionTemplate) -> list[Exercise]:
    return (
        db.query(Exercise)
        .join(TemplateExercise, TemplateExercise.exercise_id == Exercise.id)
        .filter(TemplateExercise.template_id == template.id)
        .order_by(TemplateExercise.position)
        .all()
    )
