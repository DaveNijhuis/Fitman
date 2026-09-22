"""Fill in derived fields for measurements stored without them (#325).

Before #325 the formulas refused to run without trunk impedance, which scale
weigh-ins never have (#320), so those rows kept their raw inputs — weight, the
scale's body fat, impedances — and no derived fields. Runs at startup; only
rows whose derived fields are empty are touched, and no value is overwritten.
"""

import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import settings
from models.measurement import BodyMeasurement
from models.user import User
from routers.measurements import _SEX_MAP, _apply_formulae, derive

logger = logging.getLogger(__name__)

# Fields that rows derived before #344 lack: new (muscle and bone mass), or
# empty until then for scale weigh-ins (skeletal muscle needed trunk impedance).
_ADDED_IN_344 = ("muscle_mass_kg", "bone_mass_kg", "skeletal_muscle_kg", "smi")


def backfill_derived(db: Session) -> int:
    """Derive what can be derived for rows that lack it; returns how many rows changed.

    Rows with nothing derived get everything. Rows derived before #344 get only
    the fields added then, and only where empty: a value already stored is never
    overwritten, even where today's formulas would give another.
    """
    candidates = (
        db.query(BodyMeasurement, User)
        .join(User, User.id == BodyMeasurement.user_id)
        .filter(
            or_(
                BodyMeasurement.bmi.is_(None),  # always set when anything is derived
                BodyMeasurement.muscle_mass_kg.is_(None),
            ),
            BodyMeasurement.weight_kg.isnot(None),
            BodyMeasurement.body_fat_pct.isnot(None),
        )
        .all()
    )
    filled = 0
    for measurement, user in candidates:
        # The same fallbacks as logging a measurement, but the age at the time
        # of the measurement rather than today's.
        if user.birth_year:
            age: int | None = measurement.recorded_at.year - user.birth_year
        else:
            age = settings.scale_age or None
        sex = _SEX_MAP.get(user.sex or "", settings.scale_sex)
        if measurement.bmi is None:
            if measurement.height_cm is None and user.height_cm:
                measurement.height_cm = user.height_cm
            _apply_formulae(measurement, age, sex)
            filled += measurement.bmi is not None
            continue
        derived = derive(measurement, age, sex)
        if derived is None:
            continue
        added = [f for f in _ADDED_IN_344 if getattr(measurement, f) is None]
        for field in added:
            setattr(measurement, field, derived[field])
        filled += bool(added)
    db.commit()
    if filled:
        logger.info("Filled derived fields for %d stored measurement(s)", filled)
    return filled
