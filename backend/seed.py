from typing import TypedDict

from sqlalchemy.orm import Session

from models.exercise import Exercise
from models.template import SessionTemplate, TemplateExercise

EXERCISES = [
    # Push A
    {
        "name": "Flat DB Bench Press",
        "muscles": "Chest, Front Delt, Triceps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Incline DB Press",
        "muscles": "Upper Chest, Front Delt, Triceps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Seated DB Shoulder Press",
        "muscles": "Front Delt, Side Delt, Triceps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Lateral Raise",
        "muscles": "Side Delt",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Overhead Triceps Extension",
        "muscles": "Triceps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Push-Up",
        "muscles": "Chest, Front Delt, Triceps",
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    {
        "name": "Chest Dip",
        "muscles": "Chest, Triceps",
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    # Pull A
    {
        "name": "One-Arm DB Row",
        "muscles": "Lats, Biceps, Rear Delt",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Chest-Supported DB Row",
        "muscles": "Lats, Rear Delt, Biceps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Pullover",
        "muscles": "Lats, Chest",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Rear Delt Fly",
        "muscles": "Rear Delt, Traps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Incline DB Curl",
        "muscles": "Biceps",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Hammer Curl",
        "muscles": "Biceps, Brachialis",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Pull-Up",
        "muscles": "Lats, Biceps, Rear Delt",
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    # Legs A
    {
        "name": "DB Goblet Squat",
        "muscles": "Quads, Glutes",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Bulgarian Split Squat",
        "muscles": "Quads, Glutes",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "DB Reverse Lunge",
        "muscles": "Quads, Glutes, Hamstrings",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Romanian Deadlift",
        "muscles": "Hamstrings, Glutes, Lower Back",
        "type": "weight",
        "equip": "Dumbbell",
    },
    {
        "name": "Glute Bridge",
        "muscles": "Glutes, Hamstrings",
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
    {
        "name": "Single-Leg Calf Raise",
        "muscles": "Calves",
        "type": "bodyweight",
        "equip": "Bodyweight",
    },
]


# Built-in session templates, in display order (#354). The migration that
# introduced templates writes the same names, focus and colours.
class _Template(TypedDict):
    name: str
    focus: str
    colour: str
    exercises: list[str]


TEMPLATES: list[_Template] = [
    {
        "name": "Push A",
        "focus": "Chest · Shoulders · Triceps",
        "colour": "#ff5a36",
        "exercises": [
            "Flat DB Bench Press",
            "Incline DB Press",
            "Seated DB Shoulder Press",
            "DB Lateral Raise",
            "Overhead Triceps Extension",
            "Push-Up",
            "Chest Dip",
        ],
    },
    {
        "name": "Pull A",
        "focus": "Back · Biceps · Rear Delts",
        "colour": "#3b82f6",
        "exercises": [
            "One-Arm DB Row",
            "Chest-Supported DB Row",
            "DB Pullover",
            "DB Rear Delt Fly",
            "Incline DB Curl",
            "DB Hammer Curl",
            "Pull-Up",
        ],
    },
    {
        "name": "Legs A",
        "focus": "Quads · Glutes · Hamstrings",
        "colour": "#1f9d62",
        "exercises": [
            "DB Goblet Squat",
            "Bulgarian Split Squat",
            "DB Reverse Lunge",
            "Romanian Deadlift",
            "Glute Bridge",
            "Single-Leg Calf Raise",
        ],
    },
]


def seed_exercises(db: Session) -> None:
    """Seed the library and the built-in templates, each only if absent.

    Separate checks, because the templates migration finds no exercises on a
    fresh install and so creates no templates; this fills in both. On an
    upgraded install the migration made the templates and this does nothing.
    """
    if not db.query(Exercise).first():
        db.add_all([Exercise(**e) for e in EXERCISES])
        db.flush()

    if not db.query(SessionTemplate).filter(SessionTemplate.user_id.is_(None)).first():
        ids = {name: id_ for id_, name in db.query(Exercise.id, Exercise.name)}
        for position, t in enumerate(TEMPLATES):
            template = SessionTemplate(
                name=t["name"], focus=t["focus"], colour=t["colour"], position=position
            )
            template.exercises = [
                TemplateExercise(exercise_id=ids[name], position=i)
                for i, name in enumerate(t["exercises"])
            ]
            db.add(template)

    db.commit()
