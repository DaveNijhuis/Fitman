"""add custom exercises: exercises.user_id and archived_at

Revision ID: o1p3q5r7s9t1
Revises: n0o2p4q6r8s0
Create Date: 2026-09-27

A user adds their own exercises (#358). user_id NULL is a built-in, as every
existing row is; deleting a user removes theirs. archived_at is set when a
logged custom exercise is deleted: hidden from the library, history kept.

Erasing a user now cascades to their custom exercises and, separately, via
their workouts to the logs and template rows pointing at those exercises.
PostgreSQL checks a NO ACTION key after each cascade step, so it saw the
exercise gone while its logs were still there, and refused. The two keys into
exercises are checked at commit instead, when both cascades have run. Nothing
new cascades: deleting an exercise still never takes a log with it.

Downgrade drops both columns, and first every custom exercise with the logs
recorded against it — the old shape has no owner to give them. Built-ins and
their history are untouched.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "o1p3q5r7s9t1"
down_revision: Union[str, None] = "n0o2p4q6r8s0"
branch_labels = None
depends_on = None


DEFERRED_KEYS = [
    ("logs", "logs_exercise_id_fkey"),
    ("template_exercises", "template_exercises_exercise_id_fkey"),
]


def _exercise_keys(deferred: bool) -> None:
    for table, name in DEFERRED_KEYS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name,
            table,
            "exercises",
            ["exercise_id"],
            ["id"],
            deferrable=deferred or None,
            initially="DEFERRED" if deferred else None,
        )


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_exercises_user_id", "exercises", ["user_id"])
    op.add_column(
        "exercises",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    _exercise_keys(deferred=True)


def downgrade() -> None:
    conn = op.get_bind()
    custom = "SELECT id FROM exercises WHERE user_id IS NOT NULL"
    conn.execute(sa.text(f"DELETE FROM logs WHERE exercise_id IN ({custom})"))
    conn.execute(
        sa.text(f"DELETE FROM template_exercises WHERE exercise_id IN ({custom})")
    )
    conn.execute(sa.text("DELETE FROM exercises WHERE user_id IS NOT NULL"))
    # The deletes above leave deferred key checks pending, and PostgreSQL won't
    # alter a table with checks outstanding: run them now.
    conn.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    _exercise_keys(deferred=False)
    op.drop_column("exercises", "archived_at")
    op.drop_index("ix_exercises_user_id", table_name="exercises")
    op.drop_column("exercises", "user_id")
