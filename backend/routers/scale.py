"""The backend's side of a smart scale weigh-in (#323). Opt-in: #326.

The phone relays over Web Bluetooth (#322): each request carries the frames
the scale sent, and the response carries the frames to write back to FFB1.
The handshake is built from the logged-in user's own profile — the scale
computes body fat from it — and a result is stored for that user only if the
scale tagged it with their scale user id.

The handshake's state (next phone sequence number, whether the profile went
out) travels with the phone, so nothing is held here between requests.
"""

import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from features import require_scale_enabled
from models.measurement import BodyMeasurement
from models.user import User
from routers.measurements import _SEX_MAP, MeasurementOut, _apply_formulae
from scale import protocol
from scale.handshake import Handshake, ScaleProfile

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/scale",
    tags=["scale"],
    dependencies=[Depends(require_scale_enabled)],
)

_MAX_FRAME_BYTES = 64  # the largest scale frame seen is 43 bytes


class ExchangeIn(BaseModel):
    frames: list[str] = Field(default_factory=list, max_length=20)
    phone_seq: int = Field(default=0, ge=0, le=0xFFFF)
    sequence_sent: bool = False
    # The phone's offset from UTC: the container runs in UTC, and the scale
    # shows its clock to the user.
    utc_offset_min: int = Field(default=0, ge=-720, le=840)

    @field_validator("frames")
    @classmethod
    def _frames_parse(cls, frames: list[str]) -> list[str]:
        for text in frames:
            try:
                raw = bytes.fromhex(text)
            except ValueError:
                raise ValueError(f"frame is not hex: {text[:20]!r}") from None
            if len(raw) > _MAX_FRAME_BYTES:
                raise ValueError(f"frame is {len(raw)} bytes, over {_MAX_FRAME_BYTES}")
            protocol.parse(raw)  # length and check byte; ValueError → 422
        return frames


class ExchangeOut(BaseModel):
    send: list[str]  # hex frames to write to FFB1, in order
    phone_seq: int
    sequence_sent: bool
    measurement: MeasurementOut | None = None
    error: str | None = None


def _profile(user: User) -> tuple[int, int, int]:
    """(height cm, age, sex code) — or 422 naming everything missing.

    No fallback values: the scale computes body fat from what is sent.
    """
    missing = []
    if not user.height_cm:
        missing.append("height")
    if not user.birth_year:
        missing.append("birth year")
    if user.sex not in _SEX_MAP:
        missing.append("sex (male or female)")
    if missing or user.height_cm is None or user.birth_year is None or user.sex is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Complete your profile before weighing in: {', '.join(missing)}",
        )
    age = datetime.now(timezone.utc).year - user.birth_year
    return round(user.height_cm), age, _SEX_MAP[user.sex]


def _scale_user_id(user: User, db: Session) -> bytes:
    if user.scale_user_id is None:
        while True:
            candidate = secrets.token_bytes(4)
            if candidate == bytes(4):
                continue  # all zeros is the scale's "no user"
            taken = db.query(User).filter(User.scale_user_id == candidate.hex()).first()
            if taken is None:
                break
        user.scale_user_id = candidate.hex()
        db.commit()
    return bytes.fromhex(user.scale_user_id)


def _last_weight(user: User, db: Session) -> float | None:
    latest = (
        db.query(BodyMeasurement)
        .filter(
            BodyMeasurement.user_id == user.id, BodyMeasurement.weight_kg.isnot(None)
        )
        .order_by(BodyMeasurement.recorded_at.desc())
        .first()
    )
    return latest.weight_kg if latest else None


def _store(
    result: protocol.Measurement, user: User, age: int, sex: int, db: Session
) -> BodyMeasurement:
    m = BodyMeasurement(
        user_id=user.id,
        recorded_at=datetime.now(timezone.utc),
        weight_kg=result.weight_kg,
        height_cm=user.height_cm,
        body_fat_pct=result.body_fat_pct,
        ra_z20=result.ra_z20,
        la_z20=result.la_z20,
        rl_z20=result.rl_z20,
        ll_z20=result.ll_z20,
        ra_z100=result.ra_z100,
        la_z100=result.la_z100,
        rl_z100=result.rl_z100,
        ll_z100=result.ll_z100,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    # Derived fields stay empty while trunk impedance is unresolved (#325).
    _apply_formulae(m, age, sex)
    db.commit()
    db.refresh(m)
    return m


@router.post("/exchange", response_model=ExchangeOut)
def exchange(
    body: ExchangeIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ExchangeOut:
    height_cm, age, sex = _profile(user)
    uid = _scale_user_id(user, db)
    last = _last_weight(user, db)
    try:
        hs = Handshake(
            ScaleProfile(
                height_cm=height_cm,
                age=age,
                male=sex == 1,
                last_weight_kg=last,
                prev_weight_kg=last,
                target_weight_kg=None,
                user_id=uid,
            ),
            utc_offset_min=body.utc_offset_min,
            seq=body.phone_seq,
            sent_sequence=body.sequence_sent,
        )
        frames = [protocol.parse(bytes.fromhex(f)) for f in body.frames]
        send = hs.start() if not frames else []
        for f in frames:
            send += hs.on_scale_frame(f)
    except ValueError as err:  # e.g. a height the scale can't represent
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err

    measurement: BodyMeasurement | None = None
    error: str | None = None
    if hs.result is not None:
        if hs.result.user_id == uid:
            measurement = _store(hs.result, user, age, sex, db)
        else:
            # Still acknowledged above, or the scale keeps re-sending it.
            error = "The scale attributed this weigh-in to a different scale user; not stored."
            logger.warning(
                "scale result for %s, expected %s", hs.result.user_id.hex(), uid.hex()
            )

    return ExchangeOut(
        send=[f.hex() for f in send],
        phone_seq=hs.seq,
        sequence_sent=hs.sent_sequence,
        measurement=MeasurementOut.model_validate(measurement) if measurement else None,
        error=error,
    )
