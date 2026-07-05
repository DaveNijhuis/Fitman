"""add user_id to workout_sessions, cardio_entries, body_measurements

Revision ID: b3d7f9e1c4a2
Revises: a1c3e5f7b2d4
Create Date: 2026-07-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3d7f9e1c4a2"
down_revision: Union[str, None] = "a1c3e5f7b2d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add user_id with server_default=1 so existing rows are assigned to the first user
    op.add_column(
        "workout_sessions",
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "cardio_entries",
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "body_measurements",
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    # SQLite does not support DROP COLUMN directly; recreate tables without user_id
    with op.batch_alter_table("workout_sessions") as batch_op:
        batch_op.drop_column("user_id")
    with op.batch_alter_table("cardio_entries") as batch_op:
        batch_op.drop_column("user_id")
    with op.batch_alter_table("body_measurements") as batch_op:
        batch_op.drop_column("user_id")
