"""add Push B, Pull B and Legs B built-in templates

Revision ID: n0o2p4q6r8s0
Revises: m9n1o3p5q7r9
Create Date: 2026-09-27

The B days follow Legacy Muscle's dumbbell-only 6-day push/pull/legs
(#357), mapped onto the library: seven of its exercises are added here, the
rest already exist — some in an A day, which keeps one history for them.
Colours follow the category, so each B day takes its A day's.

On a fresh install the library is still empty here and the startup seed
creates everything, so nothing happens then. Names already present are
skipped, exercises and templates alike.

Downgrade removes the three templates (their workouts keep their name and
lose only the link) and the added exercises nobody has logged or used.

The data is copied, not imported from seed.py: a migration must keep doing
what it did when it ran, whatever seed.py becomes.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "n0o2p4q6r8s0"
down_revision: Union[str, None] = "m9n1o3p5q7r9"
branch_labels = None
depends_on = None


def _e(name: str, muscles: str) -> dict[str, str]:
    return {"name": name, "muscles": muscles, "type": "weight", "equip": "Dumbbell"}


EXERCISES = [
    _e("DB Front Raise", "Front Delt"),
    _e("DB High Row", "Rear Delt, Traps"),
    _e("Renegade Row", "Lats, Rear Delt, Biceps"),
    _e("DB Curl", "Biceps"),
    _e("DB Reverse Curl", "Brachialis, Biceps"),
    _e("DB Stiff-Legged Deadlift", "Hamstrings, Glutes, Lower Back"),
    _e("DB Lateral Lunge", "Quads, Glutes"),
]

TEMPLATES = [
    {
        "name": "Push B",
        "focus": "Shoulders · Chest · Triceps",
        "colour": "#ff5a36",
        "exercises": [
            "Arnold Press",
            "DB Front Raise",
            "Push-Up",
            "DB Pullover",
            "DB Skull Crusher",
        ],
    },
    {
        "name": "Pull B",
        "focus": "Back · Traps · Biceps",
        "colour": "#3b82f6",
        "exercises": [
            "DB High Row",
            "Renegade Row",
            "DB Shrug",
            "DB Curl",
            "DB Reverse Curl",
        ],
    },
    {
        "name": "Legs B",
        "focus": "Hamstrings · Glutes · Quads",
        "colour": "#1f9d62",
        "exercises": [
            "DB Goblet Squat",
            "DB Stiff-Legged Deadlift",
            "DB Lateral Lunge",
            "DB Hip Thrust",
            "Seated DB Calf Raise",
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    if not conn.execute(sa.text("SELECT EXISTS (SELECT 1 FROM exercises)")).scalar():
        return

    for e in EXERCISES:
        conn.execute(
            sa.text(
                "INSERT INTO exercises (name, muscles, type, equip) "
                "SELECT :name, :muscles, :type, :equip "
                "WHERE NOT EXISTS (SELECT 1 FROM exercises WHERE name = :name)"
            ),
            e,
        )

    for t in TEMPLATES:
        exists = conn.execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM session_templates "
                "WHERE user_id IS NULL AND name = :name)"
            ),
            {"name": t["name"]},
        ).scalar()
        if exists:
            continue
        ids = []
        for name in t["exercises"]:
            exercise_id = conn.execute(
                sa.text("SELECT min(id) FROM exercises WHERE name = :name"),
                {"name": name},
            ).scalar()
            if exercise_id is None:
                # Every one is seeded, or added by #356 or above; a gap means the
                # library isn't what this migration was written against. Stop
                # rather than create a B day short of an exercise.
                raise RuntimeError(f"{t['name']} needs {name!r}, which is missing")
            ids.append(exercise_id)
        template_id = conn.execute(
            sa.text(
                "INSERT INTO session_templates (name, focus, colour, position) "
                "SELECT :name, :focus, :colour, coalesce(max(position) + 1, 0) "
                "FROM session_templates WHERE user_id IS NULL RETURNING id"
            ),
            {"name": t["name"], "focus": t["focus"], "colour": t["colour"]},
        ).scalar_one()
        for position, exercise_id in enumerate(ids):
            conn.execute(
                sa.text(
                    "INSERT INTO template_exercises (template_id, exercise_id, position) "
                    "VALUES (:t, :e, :p)"
                ),
                {"t": template_id, "e": exercise_id, "p": position},
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM session_templates WHERE user_id IS NULL AND name = ANY(:names)"
        ),
        {"names": [t["name"] for t in TEMPLATES]},
    )
    conn.execute(
        sa.text(
            "DELETE FROM exercises e WHERE e.name = ANY(:names) "
            "AND NOT EXISTS (SELECT 1 FROM logs l WHERE l.exercise_id = e.id) "
            "AND NOT EXISTS "
            "(SELECT 1 FROM template_exercises te WHERE te.exercise_id = e.id)"
        ),
        {"names": [e["name"] for e in EXERCISES]},
    )
