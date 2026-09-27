"""add 21 exercises to the built-in library

Revision ID: m9n1o3p5q7r9
Revises: l8m0n2o4p6q8
Create Date: 2026-09-27

Dumbbell and bodyweight exercises for B days and user-made days (#356).
seed_exercises returns as soon as any exercise exists, so these would never
reach a running install through seed.py alone; seed.py carries the same list
to a fresh one.

On a fresh install the library is still empty here, and adding these would
make the seed skip the original twenty — so nothing happens then. Names
already present are skipped.

Downgrade removes only the ones nobody has logged or put in a template: the
others would take a user's sets with them.

The list is copied, not imported from seed.py: a migration must keep doing
what it did when it ran, whatever seed.py becomes.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "m9n1o3p5q7r9"
down_revision: Union[str, None] = "l8m0n2o4p6q8"
branch_labels = None
depends_on = None


def _e(name: str, muscles: str, type_: str = "weight") -> dict[str, str]:
    equip = "Dumbbell" if type_ == "weight" else "Bodyweight"
    return {"name": name, "muscles": muscles, "type": type_, "equip": equip}


EXERCISES = [
    # Push
    _e("Arnold Press", "Front Delt, Side Delt, Triceps"),
    _e("Low-Incline DB Press", "Upper Chest, Chest, Front Delt, Triceps"),
    _e("Close-Grip DB Press", "Triceps, Chest, Front Delt"),
    _e("Lean-Away Lateral Raise", "Side Delt"),
    _e("DB Skull Crusher", "Triceps"),
    _e("Pike Push-Up", "Front Delt, Side Delt, Triceps", "bodyweight"),
    _e("Diamond Push-Up", "Triceps, Chest", "bodyweight"),
    # Pull
    _e("Two-Arm Bent-Over DB Row", "Lats, Rear Delt, Biceps"),
    _e("DB Seal Row", "Lats, Rear Delt, Traps"),
    _e("DB Shrug", "Traps"),
    _e("Prone Y-T-W Raise", "Rear Delt, Traps"),
    _e("Zottman Curl", "Biceps, Brachialis"),
    _e("Concentration Curl", "Biceps"),
    _e("Chin-Up", "Lats, Biceps", "bodyweight"),
    # Legs
    _e("Single-Leg RDL", "Hamstrings, Glutes"),
    _e("DB Step-Up", "Quads, Glutes"),
    _e("DB Sumo Squat", "Quads, Glutes"),
    _e("DB Hip Thrust", "Glutes, Hamstrings"),
    _e("Cossack Squat", "Quads, Glutes", "bodyweight"),
    _e("Nordic Curl", "Hamstrings", "bodyweight"),
    _e("Seated DB Calf Raise", "Calves"),
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


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM exercises e WHERE e.name = ANY(:names) "
            "AND NOT EXISTS (SELECT 1 FROM logs l WHERE l.exercise_id = e.id) "
            "AND NOT EXISTS "
            "(SELECT 1 FROM template_exercises te WHERE te.exercise_id = e.id)"
        ),
        {"names": [e["name"] for e in EXERCISES]},
    )
