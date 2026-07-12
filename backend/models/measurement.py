from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class BodyMeasurement(Base):
    __tablename__ = "body_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ── Basic ──────────────────────────────────────────────────────────────────
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(String)

    # ── Whole-body composition ─────────────────────────────────────────────────
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    fat_mass_kg: Mapped[float | None] = mapped_column(Float)
    lean_mass_kg: Mapped[float | None] = mapped_column(Float)
    skeletal_muscle_kg: Mapped[float | None] = mapped_column(Float)
    fat_free_weight_kg: Mapped[float | None] = mapped_column(Float)
    body_water_pct: Mapped[float | None] = mapped_column(Float)
    protein_kg: Mapped[float | None] = mapped_column(Float)
    inorganic_salt_kg: Mapped[float | None] = mapped_column(Float)
    bmr_kcal: Mapped[float | None] = mapped_column(Float)
    visceral_fat_grade: Mapped[float | None] = mapped_column(Float)
    subcutaneous_fat_pct: Mapped[float | None] = mapped_column(Float)
    body_age: Mapped[int | None] = mapped_column(Integer)
    whr_estimate: Mapped[float | None] = mapped_column(Float)
    smi: Mapped[float | None] = mapped_column(Float)

    # ── Segmental fat (kg) ────────────────────────────────────────────────────
    ra_fat_kg: Mapped[float | None] = mapped_column(Float)
    la_fat_kg: Mapped[float | None] = mapped_column(Float)
    trunk_fat_kg: Mapped[float | None] = mapped_column(Float)
    rl_fat_kg: Mapped[float | None] = mapped_column(Float)
    ll_fat_kg: Mapped[float | None] = mapped_column(Float)

    # ── Segmental muscle (kg) ─────────────────────────────────────────────────
    ra_muscle_kg: Mapped[float | None] = mapped_column(Float)
    la_muscle_kg: Mapped[float | None] = mapped_column(Float)
    trunk_muscle_kg: Mapped[float | None] = mapped_column(Float)
    rl_muscle_kg: Mapped[float | None] = mapped_column(Float)
    ll_muscle_kg: Mapped[float | None] = mapped_column(Float)

    # ── Raw impedance — 20 kHz (Ω) ────────────────────────────────────────────
    ra_z20: Mapped[float | None] = mapped_column(Float)
    la_z20: Mapped[float | None] = mapped_column(Float)
    rl_z20: Mapped[float | None] = mapped_column(Float)
    ll_z20: Mapped[float | None] = mapped_column(Float)
    trunk_z20: Mapped[float | None] = mapped_column(Float)

    # ── Raw impedance — 100 kHz (Ω) ───────────────────────────────────────────
    ra_z100: Mapped[float | None] = mapped_column(Float)
    la_z100: Mapped[float | None] = mapped_column(Float)
    rl_z100: Mapped[float | None] = mapped_column(Float)
    ll_z100: Mapped[float | None] = mapped_column(Float)
    trunk_z100: Mapped[float | None] = mapped_column(Float)
