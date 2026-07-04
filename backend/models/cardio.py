from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base, TZDateTime


class CardioSession(Base):
    __tablename__ = "cardio_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime)

    logs: Mapped[list["CardioLog"]] = relationship(
        "CardioLog", back_populates="cardio_session"
    )


class CardioLog(Base):
    __tablename__ = "cardio_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cardio_sessions.id"), nullable=False
    )
    activity: Mapped[str] = mapped_column(String, nullable=False)
    distance_m: Mapped[float | None] = mapped_column(Float)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String)
    logged_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)

    cardio_session: Mapped["CardioSession"] = relationship(
        "CardioSession", back_populates="logs"
    )
