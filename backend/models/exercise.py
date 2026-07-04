from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    muscles: Mapped[str | None] = mapped_column(String)
    session: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    type: Mapped[str] = mapped_column(String, nullable=False)  # "weight" | "bodyweight"
    equip: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "Dumbbell" | "Bodyweight"
