from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.cardio import CardioEntry
from models.measurement import BodyMeasurement
from models.user import User
from models.workout import Log, WorkoutSession

router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


@router.delete("/erase", status_code=status.HTTP_204_NO_CONTENT)
def erase_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_id = current_user.id
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
    db.delete(current_user)
    db.commit()
