from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.cardio import CardioLog, CardioSession

router = APIRouter(prefix="/api/cardio", tags=["cardio"])

ACTIVITIES = ["Run", "Walk", "Bike", "Swim", "Row", "Other"]


class CardioIn(BaseModel):
    activity: str
    distance_m: float | None = None
    duration_s: int | None = None
    notes: str | None = None
    logged_at: datetime | None = None


class CardioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    activity: str
    distance_m: float | None
    duration_s: int | None
    notes: str | None
    logged_at: datetime


@router.get("/activities")
def list_activities(_: str = Depends(get_current_user)) -> list[str]:
    return ACTIVITIES


@router.post("", response_model=CardioOut, status_code=status.HTTP_201_CREATED)
def log_cardio(
    body: CardioIn,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    if body.activity not in ACTIVITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown activity"
        )

    now = body.logged_at or datetime.now(timezone.utc)

    session = CardioSession(started_at=now, ended_at=now)
    db.add(session)
    db.flush()

    log = CardioLog(
        session_id=session.id,
        activity=body.activity,
        distance_m=body.distance_m,
        duration_s=body.duration_s,
        notes=body.notes,
        logged_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("", response_model=list[CardioOut])
def list_cardio(
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    return db.query(CardioLog).order_by(CardioLog.logged_at.desc()).all()


@router.delete("/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cardio(
    log_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(get_current_user),
):
    log = db.get(CardioLog, log_id)
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )
    session = db.get(CardioSession, log.session_id)
    db.delete(log)
    if session:
        db.delete(session)
    db.commit()
