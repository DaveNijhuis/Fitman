from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # NULL is a built-in, visible to everyone; otherwise the user's own (#358).
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    muscles: Mapped[str | None] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, nullable=False)  # "weight" | "bodyweight"
    equip: Mapped[str] = mapped_column(String, nullable=False)  # free text (#358)
    # Set when a logged custom exercise is deleted: hidden from the library,
    # its history kept (#358).
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def custom(self) -> bool:
        return self.user_id is not None

    @property
    def archived(self) -> bool:
        return self.archived_at is not None
