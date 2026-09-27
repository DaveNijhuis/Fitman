from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models.template import SessionTemplate
from models.user import User
from routers.exercises import ExerciseOut
from session_templates import template_exercises, visible_templates

router = APIRouter(prefix="/api/templates", tags=["templates"])


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    focus: str | None
    colour: str | None
    builtin: bool


class TemplateDetail(TemplateOut):
    exercises: list[ExerciseOut]


def _out(template: SessionTemplate) -> TemplateOut:
    return TemplateOut(
        id=template.id,
        name=template.name,
        focus=template.focus,
        colour=template.colour,
        builtin=template.user_id is None,
    )


@router.get("")
def list_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TemplateOut]:
    return [_out(t) for t in visible_templates(db, current_user)]


@router.get("/{template_id}")
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateDetail:
    template = (
        visible_templates(db, current_user)
        .filter(SessionTemplate.id == template_id)
        .first()
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
        )
    return TemplateDetail(
        **_out(template).model_dump(),
        exercises=[
            ExerciseOut.model_validate(e) for e in template_exercises(db, template)
        ],
    )
