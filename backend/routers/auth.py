from datetime import datetime, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import create_access_token
from database import get_db
from models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SetupRequired(BaseModel):
    required: bool


@router.get("/setup-required", response_model=SetupRequired)
def setup_required(db: Session = Depends(get_db)):
    """Returns true if no users exist yet — used to trigger the first-run setup page."""
    return SetupRequired(required=db.query(User).count() == 0)


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    """Create the first user. Returns 409 if any users already exist (use admin panel instead)."""
    if db.query(User).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Setup already complete. Use the admin panel to add more users.",
        )
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Username already taken"
        )

    user = User(
        username=body.username,
        hashed_password=_hash_password(body.password),
        display_name=body.display_name,
        is_active=True,
        is_admin=True,  # first user is always admin
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if (
        not user
        or not user.is_active
        or not _verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return TokenResponse(access_token=create_access_token(user.id))
