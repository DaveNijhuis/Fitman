import logging
import os
from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from formulas import ImpedanceInputs, UserProfile, calculate_all
from models.measurement import BodyMeasurement
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/measurements", tags=["measurements"])

_SEX_MAP = {"male": 1, "female": 0}


class _MeasurementFields(BaseModel):
    """All stored measurement fields — shared by input and output schemas."""

    recorded_at: datetime | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    notes: str | None = None
    body_fat_pct: float | None = None
    bmi: float | None = None
    fat_mass_kg: float | None = None
    lean_mass_kg: float | None = None
    skeletal_muscle_kg: float | None = None
    fat_free_weight_kg: float | None = None
    body_water_pct: float | None = None
    protein_kg: float | None = None
    inorganic_salt_kg: float | None = None
    bmr_kcal: float | None = None
    visceral_fat_grade: float | None = None
    subcutaneous_fat_pct: float | None = None
    body_age: int | None = None
    whr_estimate: float | None = None
    smi: float | None = None
    ra_fat_kg: float | None = None
    la_fat_kg: float | None = None
    trunk_fat_kg: float | None = None
    rl_fat_kg: float | None = None
    ll_fat_kg: float | None = None
    ra_muscle_kg: float | None = None
    la_muscle_kg: float | None = None
    trunk_muscle_kg: float | None = None
    rl_muscle_kg: float | None = None
    ll_muscle_kg: float | None = None
    ra_z20: float | None = None
    la_z20: float | None = None
    rl_z20: float | None = None
    ll_z20: float | None = None
    trunk_z20: float | None = None
    ra_z100: float | None = None
    la_z100: float | None = None
    rl_z100: float | None = None
    ll_z100: float | None = None
    trunk_z100: float | None = None


class MeasurementIn(_MeasurementFields):
    # Transient — used for formula calculation, not stored in DB
    user_age: int | None = None
    user_sex: int | None = None  # 1 = male, 0 = female


class MeasurementOut(_MeasurementFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime


class MeasurementPage(BaseModel):
    items: list[MeasurementOut]
    total: int
    page: int
    page_size: int


def _apply_formulae(measurement: BodyMeasurement, age: int | None, sex: int) -> None:
    """If all required inputs are present, calculate and fill derived fields."""
    _env_h = float(os.getenv("SCALE_HEIGHT_CM", "0"))
    height: float | None = measurement.height_cm or (_env_h or None)

    required = [
        age,
        height,
        measurement.weight_kg,
        measurement.body_fat_pct,
        measurement.ra_z20,
        measurement.la_z20,
        measurement.rl_z20,
        measurement.ll_z20,
        measurement.trunk_z20,
        measurement.ra_z100,
        measurement.la_z100,
        measurement.rl_z100,
        measurement.ll_z100,
        measurement.trunk_z100,
    ]
    if not all(x is not None for x in required):
        return

    profile = UserProfile(
        age=cast(int, age),
        height_cm=cast(float, height),
        sex=sex,
        weight_kg=cast(float, measurement.weight_kg),
    )
    inputs = ImpedanceInputs(
        ra_z20=cast(float, measurement.ra_z20),
        la_z20=cast(float, measurement.la_z20),
        rl_z20=cast(float, measurement.rl_z20),
        ll_z20=cast(float, measurement.ll_z20),
        trunk_z20=cast(float, measurement.trunk_z20),
        ra_z100=cast(float, measurement.ra_z100),
        la_z100=cast(float, measurement.la_z100),
        rl_z100=cast(float, measurement.rl_z100),
        ll_z100=cast(float, measurement.ll_z100),
        trunk_z100=cast(float, measurement.trunk_z100),
        body_fat_pct=cast(float, measurement.body_fat_pct),
    )
    derived = calculate_all(profile, inputs)
    for field, value in derived.items():
        setattr(measurement, field, value)


@router.post("", response_model=MeasurementOut, status_code=status.HTTP_201_CREATED)
def log_measurement(
    body: MeasurementIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = body.model_dump()
    age_from_request = data.pop("user_age")
    sex_from_request = data.pop("user_sex")
    data["recorded_at"] = data["recorded_at"] or datetime.now(timezone.utc)
    data["user_id"] = current_user.id
    measurement = BodyMeasurement(**data)

    # Profile fallback for height
    if measurement.height_cm is None and current_user.height_cm:
        measurement.height_cm = current_user.height_cm

    # Age: request → profile birth_year → env (0 means not configured → None)
    age: int | None
    if age_from_request:
        age = age_from_request
    elif current_user.birth_year:
        age = datetime.now(timezone.utc).year - current_user.birth_year
    else:
        age = int(os.getenv("SCALE_AGE", "0")) or None

    # Sex: request → profile sex → env
    if sex_from_request is not None:
        sex = sex_from_request
    elif current_user.sex in _SEX_MAP:
        sex = _SEX_MAP[current_user.sex]
    else:
        sex = int(os.getenv("SCALE_SEX", "1"))
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    _apply_formulae(measurement, age, sex)
    db.commit()
    db.refresh(measurement)
    return measurement


@router.get("", response_model=MeasurementPage)
def list_measurements(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(BodyMeasurement)
        .filter(BodyMeasurement.user_id == current_user.id)
        .order_by(BodyMeasurement.recorded_at.desc())
    )
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/{measurement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    measurement = db.get(BodyMeasurement, measurement_id)
    if not measurement or measurement.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Measurement not found"
        )
    db.delete(measurement)
    db.commit()
