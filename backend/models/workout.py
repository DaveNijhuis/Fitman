from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The template's name when the workout was started, so history still reads
    # right after a template is renamed or deleted (template_id then goes NULL).
    session: Mapped[str] = mapped_column(String, nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("session_templates.id", ondelete="SET NULL"), index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    logs: Mapped[list["Log"]] = relationship("Log", back_populates="workout_session")


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exercise_id: Mapped[int] = mapped_column(
        Integer,
        # Checked at commit, not per cascade step: erasing a user removes their
        # custom exercises and their workouts' rows in separate cascades (#358).
        ForeignKey("exercises.id", deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    reps: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    workout_session: Mapped["WorkoutSession"] = relationship(
        "WorkoutSession", back_populates="logs"
    )


class WorkoutExercise(Base):
    """A workout's exercise list, fixed when it started (#359).

    Editing or deleting its template leaves a workout as it began.
    """

    __tablename__ = "workout_exercises"
    __table_args__ = (UniqueConstraint("workout_session_id", "exercise_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workout_session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("workout_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exercise_id: Mapped[int] = mapped_column(
        Integer,
        # Deferred like the other keys into exercises: erasing a user removes
        # their custom exercises and their workouts in separate cascades (#358).
        ForeignKey("exercises.id", deferrable=True, initially="DEFERRED"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
