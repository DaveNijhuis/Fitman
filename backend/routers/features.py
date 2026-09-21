from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
from config import settings
from models.user import User

router = APIRouter(prefix="/api/features", tags=["features"])


class FeaturesOut(BaseModel):
    """Optional features this instance has switched on (#326).

    The frontend asks once, rather than probing feature endpoints for 404s.
    """

    scale: bool


@router.get("", response_model=FeaturesOut)
def get_features(_: User = Depends(get_current_user)) -> FeaturesOut:
    return FeaturesOut(scale=settings.scale_enabled)
