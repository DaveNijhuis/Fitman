"""Which exercises a user may reach (#358).

Built-ins (user_id NULL) are everyone's; a custom exercise is its owner's
alone. Every route that takes an exercise id goes through here, so another
user's exercise is a 404 everywhere — never a name or a chart.
"""

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from models.exercise import Exercise
from models.user import User


def visible_exercises(db: Session, user: User) -> Query[Exercise]:
    """Built-ins plus the user's own, archived ones included (for history)."""
    return db.query(Exercise).filter(
        or_(Exercise.user_id.is_(None), Exercise.user_id == user.id)
    )


def library(db: Session, user: User) -> Query[Exercise]:
    """What the library offers: visible and not archived."""
    return visible_exercises(db, user).filter(Exercise.archived_at.is_(None))


def visible_exercise(db: Session, user: User, exercise_id: int) -> Exercise | None:
    return visible_exercises(db, user).filter(Exercise.id == exercise_id).first()
