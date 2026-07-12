import logging
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    email: str | None
    display_name: str | None
    birth_year: int | None
    sex: str | None
    height_cm: float | None
    is_admin: bool


class ProfilePatch(BaseModel):
    display_name: str | None = None
    birth_year: int | None = None
    sex: Literal["male", "female", "other"] | None = None
    height_cm: float | None = None

    @field_validator("birth_year")
    @classmethod
    def birth_year_in_range(cls, v: int | None) -> int | None:
        if v is None:
            return v
        current_year = datetime.now(timezone.utc).year
        if not (1900 <= v <= current_year):
            raise ValueError(f"birth_year must be between 1900 and {current_year}")
        return v


@router.get("", response_model=ProfileOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("", response_model=ProfileOut)
def patch_profile(
    body: ProfilePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user
