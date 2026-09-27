from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class SessionTemplate(Base):
    """A training day: an ordered pick of exercises from the library (#354).

    user_id NULL is a built-in (Push A, Pull A, Legs A), visible to everyone;
    otherwise the template belongs to that user alone.
    """

    __tablename__ = "session_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    focus: Mapped[str | None] = mapped_column(String)
    colour: Mapped[str | None] = mapped_column(String)  # "#rrggbb"
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    exercises: Mapped[list["TemplateExercise"]] = relationship(
        "TemplateExercise",
        order_by="TemplateExercise.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TemplateExercise(Base):
    __tablename__ = "template_exercises"
    __table_args__ = (UniqueConstraint("template_id", "exercise_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("session_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("exercises.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
