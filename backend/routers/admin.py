from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.cardio import CardioEntry
from models.measurement import BodyMeasurement
from models.user import User
from models.workout import Log, WorkoutSession

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return current_user


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    display_name: str | None
    is_active: bool
    is_admin: bool
    created_at: datetime


class CreateUserRequest(BaseModel):
    username: str
    password: str = Field(min_length=8)
    email: str | None = None
    display_name: str | None = None
    is_admin: bool = False


class PatchUserRequest(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    return db.query(User).order_by(User.created_at).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: CreateUserRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        )
    user = User(
        username=body.username,
        hashed_password=_hash_password(body.password),
        email=body.email,
        display_name=body.display_name,
        is_active=True,
        is_admin=body.is_admin,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: int,
    body: PatchUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if user.id == current_user.id and body.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable your own account",
        )
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(_require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    session_ids = [
        s.id
        for s in db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id)
        .all()
    ]
    if session_ids:
        db.query(Log).filter(Log.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
    db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(CardioEntry).filter(CardioEntry.user_id == user_id).delete(
        synchronize_session=False
    )
    db.query(BodyMeasurement).filter(BodyMeasurement.user_id == user_id).delete(
        synchronize_session=False
    )
    db.delete(user)
    db.commit()
