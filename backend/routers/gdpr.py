import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.cardio import CardioEntry
from models.exercise import Exercise
from models.measurement import BodyMeasurement
from models.template import HiddenTemplate, SessionTemplate
from models.user import User
from models.workout import Log, WorkoutSession
from session_templates import template_exercises

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gdpr", tags=["gdpr"])


@router.delete("/erase", status_code=status.HTTP_204_NO_CONTENT)
def erase_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    db.delete(current_user)
    db.commit()


@router.get("/export")
def export_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    user_id = current_user.id

    sessions = db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).all()
    session_ids = [s.id for s in sessions]

    logs = (
        db.query(Log).filter(Log.session_id.in_(session_ids)).all()
        if session_ids
        else []
    )
    cardio = db.query(CardioEntry).filter(CardioEntry.user_id == user_id).all()
    custom_exercises = (
        db.query(Exercise)
        .filter(Exercise.user_id == user_id)
        .order_by(Exercise.id)
        .all()
    )
    own_templates = (
        db.query(SessionTemplate)
        .filter(SessionTemplate.user_id == user_id)
        .order_by(SessionTemplate.position, SessionTemplate.id)
        .all()
    )
    hidden = (
        db.query(SessionTemplate.name)
        .join(HiddenTemplate, HiddenTemplate.template_id == SessionTemplate.id)
        .filter(HiddenTemplate.user_id == user_id)
        .order_by(SessionTemplate.position)
        .all()
    )
    measurements = (
        db.query(BodyMeasurement).filter(BodyMeasurement.user_id == user_id).all()
    )

    def _dt(v: object) -> object:
        return v.isoformat() if isinstance(v, datetime) else v

    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "username": current_user.username,
            "email": current_user.email,
            "display_name": current_user.display_name,
            "birth_year": current_user.birth_year,
            "sex": current_user.sex,
            "height_cm": current_user.height_cm,
            "is_admin": current_user.is_admin,
            "created_at": _dt(current_user.created_at),
        },
        "workout_sessions": [
            {
                "id": s.id,
                "session": s.session,
                "started_at": _dt(s.started_at),
                "ended_at": _dt(s.ended_at),
            }
            for s in sessions
        ],
        "custom_exercises": [
            {
                "id": e.id,
                "name": e.name,
                "muscles": e.muscles,
                "type": e.type,
                "equip": e.equip,
                "archived_at": _dt(e.archived_at),
            }
            for e in custom_exercises
        ],
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "focus": t.focus,
                "colour": t.colour,
                "exercises": [e.name for e in template_exercises(db, t)],
            }
            for t in own_templates
        ],
        "hidden_templates": [name for (name,) in hidden],
        "logs": [
            {
                "id": log.id,
                "session_id": log.session_id,
                "exercise_id": log.exercise_id,
                "weight": log.weight,
                "reps": log.reps,
                "logged_at": _dt(log.logged_at),
            }
            for log in logs
        ],
        "cardio": [
            {
                "id": c.id,
                "activity": c.activity,
                "distance_m": c.distance_m,
                "duration_s": c.duration_s,
                "notes": c.notes,
                "logged_at": _dt(c.logged_at),
            }
            for c in cardio
        ],
        "body_measurements": [
            {
                "id": m.id,
                "recorded_at": _dt(m.recorded_at),
                "weight_kg": m.weight_kg,
                "body_fat_pct": m.body_fat_pct,
                "height_cm": m.height_cm,
                "bmi": m.bmi,
                "fat_mass_kg": m.fat_mass_kg,
                "lean_mass_kg": m.lean_mass_kg,
                "bmr_kcal": m.bmr_kcal,
            }
            for m in measurements
        ],
    }

    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": 'attachment; filename="fitman-export.json"'},
    )
