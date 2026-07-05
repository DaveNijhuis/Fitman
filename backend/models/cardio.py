from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, TZDateTime


class CardioEntry(Base):
    __tablename__ = "cardio_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    activity: Mapped[str] = mapped_column(String, nullable=False)
    distance_m: Mapped[float | None] = mapped_column(Float)
    duration_s: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(String)
    logged_at: Mapped[datetime] = mapped_column(TZDateTime, nullable=False)
