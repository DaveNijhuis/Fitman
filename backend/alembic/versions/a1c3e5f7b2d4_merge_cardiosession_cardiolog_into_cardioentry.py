"""merge CardioSession+CardioLog into CardioEntry

Revision ID: a1c3e5f7b2d4
Revises: fb0db5c0c33b
Create Date: 2026-07-04

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1c3e5f7b2d4"
down_revision: Union[str, None] = "fb0db5c0c33b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cardio_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("activity", sa.String(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("logged_at", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Migrate existing data: each cardio_log row becomes one cardio_entry
    op.execute("""
        INSERT INTO cardio_entries (id, activity, distance_m, duration_s, notes, logged_at)
        SELECT id, activity, distance_m, duration_s, notes, logged_at
        FROM cardio_logs
    """)

    op.drop_table("cardio_logs")
    op.drop_table("cardio_sessions")


def downgrade() -> None:
    op.create_table(
        "cardio_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=False),
        sa.Column("ended_at", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "cardio_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("activity", sa.String(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("duration_s", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("logged_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["cardio_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # Restore: create a phantom session per entry then copy log data back
    op.execute("""
        INSERT INTO cardio_sessions (id, started_at, ended_at)
        SELECT id, logged_at, logged_at FROM cardio_entries
    """)
    op.execute("""
        INSERT INTO cardio_logs (id, session_id, activity, distance_m, duration_s, notes, logged_at)
        SELECT id, id, activity, distance_m, duration_s, notes, logged_at
        FROM cardio_entries
    """)

    op.drop_table("cardio_entries")
