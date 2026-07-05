from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.cardio import CardioEntry
from models.user import User

router = APIRouter(prefix="/api/cardio", tags=["cardio"])

ACTIVITIES = ["Run", "Walk", "Bike", "Swim", "Row", "Other"]


class CardioIn(BaseModel):
    activity: str
    distance_m: float | None = None
    duration_s: int | None = None
    notes: str | None = None
    logged_at: datetime | None = None


class CardioEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    activity: str
    distance_m: float | None
    duration_s: int | None
    notes: str | None
    logged_at: datetime


@router.get("/activities")
def list_activities(_: User = Depends(get_current_user)) -> list[str]:
    return ACTIVITIES


@router.post("", response_model=CardioEntryOut, status_code=status.HTTP_201_CREATED)
def log_cardio(
    body: CardioIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.activity not in ACTIVITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown activity"
        )

    entry = CardioEntry(
        user_id=current_user.id,
        activity=body.activity,
        distance_m=body.distance_m,
        duration_s=body.duration_s,
        notes=body.notes,
        logged_at=body.logged_at or datetime.now(timezone.utc),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("", response_model=list[CardioEntryOut])
def list_cardio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(CardioEntry)
        .filter(CardioEntry.user_id == current_user.id)
        .order_by(CardioEntry.logged_at.desc())
        .all()
    )


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cardio(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = db.get(CardioEntry, entry_id)
    if not entry or entry.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found"
        )
    db.delete(entry)
    db.commit()
