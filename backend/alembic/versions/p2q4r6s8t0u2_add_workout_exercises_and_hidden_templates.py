"""add workout_exercises and hidden_templates

Revision ID: p2q4r6s8t0u2
Revises: o1p3q5r7s9t1
Create Date: 2026-09-27

Users build their own days (#359), so a day can change while a workout from
it is under way. workout_exercises fixes each workout's exercise list when it
starts. Existing workouts get the list their template has now — the closest
record there is — so one in progress carries on unchanged. hidden_templates
records the built-ins a user has hidden from Home and the picker.

Downgrade drops both: workouts fall back to reading their template, and hidden
built-ins reappear.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "p2q4r6s8t0u2"
down_revision: Union[str, None] = "o1p3q5r7s9t1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "workout_session_id",
            sa.Integer(),
            sa.ForeignKey("workout_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exercise_id",
            sa.Integer(),
            # Deferred like the other keys into exercises (#358).
            sa.ForeignKey(
                "exercises.id", deferrable=True, initially="DEFERRED"
            ),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("workout_session_id", "exercise_id"),
    )
    op.create_index(
        "ix_workout_exercises_workout_session_id",
        "workout_exercises",
        ["workout_session_id"],
    )
    op.create_index(
        "ix_workout_exercises_exercise_id", "workout_exercises", ["exercise_id"]
    )
    op.create_table(
        "hidden_templates",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("session_templates.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.get_bind().execute(
        sa.text(
            "INSERT INTO workout_exercises (workout_session_id, exercise_id, position) "
            "SELECT w.id, te.exercise_id, te.position FROM workout_sessions w "
            "JOIN template_exercises te ON te.template_id = w.template_id"
        )
    )


def downgrade() -> None:
    op.drop_table("hidden_templates")
    op.drop_index("ix_workout_exercises_exercise_id", table_name="workout_exercises")
    op.drop_index(
        "ix_workout_exercises_workout_session_id", table_name="workout_exercises"
    )
    op.drop_table("workout_exercises")
