"""add session templates; exercises no longer belong to one session

Revision ID: l8m0n2o4p6q8
Revises: k7l9m1n3o5p6
Create Date: 2026-09-27

An exercise belonged to exactly one session through exercises.session, so it
could not sit in two training days without a second row — which splits its
logs, chart and records across two ids (#354). The library becomes a flat
list, and session_templates point into it through template_exercises.

Each distinct exercises.session becomes a built-in template (user_id NULL),
keeping every exercise's id and its order. Workouts are linked to their
template by name; workout_sessions.session stays as the name at the time.

On a fresh install there are no exercises yet, so no templates are made here;
the startup seed creates both.

Downgrade puts each exercise back in its first built-in template. User-owned
templates, and an exercise's membership of any template beyond its first,
have nowhere to go in the old shape and are lost.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "l8m0n2o4p6q8"
down_revision: Union[str, None] = "k7l9m1n3o5p6"
branch_labels = None
depends_on = None

# Focus and colour the frontend hard-coded for these names; seed.py matches.
KNOWN = {
    "Push A": ("Chest · Shoulders · Triceps", "#ff5a36"),
    "Pull A": ("Back · Biceps · Rear Delts", "#3b82f6"),
    "Legs A": ("Quads · Glutes · Hamstrings", "#1f9d62"),
}


def upgrade() -> None:
    op.create_table(
        "session_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("focus", sa.String(), nullable=True),
        sa.Column("colour", sa.String(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_session_templates_user_id", "session_templates", ["user_id"]
    )
    op.create_table(
        "template_exercises",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("session_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "exercise_id",
            sa.Integer(),
            sa.ForeignKey("exercises.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("template_id", "exercise_id"),
    )
    op.create_index(
        "ix_template_exercises_template_id", "template_exercises", ["template_id"]
    )
    op.create_index(
        "ix_template_exercises_exercise_id", "template_exercises", ["exercise_id"]
    )
    op.add_column(
        "workout_sessions",
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("session_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_workout_sessions_template_id", "workout_sessions", ["template_id"]
    )

    conn = op.get_bind()
    names = [
        r[0]
        for r in conn.execute(
            sa.text("SELECT DISTINCT session FROM exercises WHERE session <> ''")
        )
    ]
    ordered = [n for n in KNOWN if n in names] + sorted(set(names) - set(KNOWN))
    for position, name in enumerate(ordered):
        focus, colour = KNOWN.get(name, (None, None))
        conn.execute(
            sa.text(
                "INSERT INTO session_templates (name, focus, colour, position) "
                "VALUES (:name, :focus, :colour, :position)"
            ),
            {"name": name, "focus": focus, "colour": colour, "position": position},
        )
    conn.execute(
        sa.text(
            "INSERT INTO template_exercises (template_id, exercise_id, position) "
            "SELECT t.id, e.id, e.position FROM exercises e "
            "JOIN session_templates t ON t.name = e.session AND t.user_id IS NULL"
        )
    )
    conn.execute(
        sa.text(
            "UPDATE workout_sessions w SET template_id = t.id "
            "FROM session_templates t WHERE t.name = w.session AND t.user_id IS NULL"
        )
    )

    op.drop_column("exercises", "position")
    op.drop_column("exercises", "session")


def downgrade() -> None:
    op.add_column("exercises", sa.Column("session", sa.String(), nullable=True))
    op.add_column("exercises", sa.Column("position", sa.Integer(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE exercises e SET session = first.name, position = first.position "
            "FROM ("
            "  SELECT DISTINCT ON (te.exercise_id) te.exercise_id, t.name, te.position "
            "  FROM template_exercises te "
            "  JOIN session_templates t ON t.id = te.template_id "
            "  WHERE t.user_id IS NULL "
            "  ORDER BY te.exercise_id, t.position, t.id"
            ") AS first WHERE first.exercise_id = e.id"
        )
    )
    conn.execute(
        sa.text("UPDATE exercises SET session = '', position = 0 WHERE session IS NULL")
    )
    op.alter_column("exercises", "session", nullable=False)
    op.alter_column("exercises", "position", nullable=False)

    op.drop_index("ix_workout_sessions_template_id", table_name="workout_sessions")
    op.drop_column("workout_sessions", "template_id")
    op.drop_index(
        "ix_template_exercises_exercise_id", table_name="template_exercises"
    )
    op.drop_index(
        "ix_template_exercises_template_id", table_name="template_exercises"
    )
    op.drop_table("template_exercises")
    op.drop_index("ix_session_templates_user_id", table_name="session_templates")
    op.drop_table("session_templates")
