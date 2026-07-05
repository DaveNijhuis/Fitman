"""convert datetime columns to timestamptz

Revision ID: f1a2b3c4d5e6
Revises: e2f9a3b7c1d5
Create Date: 2026-07-05

Historical migrations created datetime columns as VARCHAR (TZDateTime's
SQLite impl).  This migration converts them to TIMESTAMPTZ on PostgreSQL.
ISO 8601 strings stored by the old SQLite backend cast cleanly to TIMESTAMPTZ.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e2f9a3b7c1d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, nullable)
_DATETIME_COLUMNS = [
    ("workout_sessions", "started_at", False),
    ("workout_sessions", "ended_at", True),
    ("logs", "logged_at", False),
    ("cardio_entries", "logged_at", False),
    ("body_measurements", "recorded_at", False),
    ("users", "created_at", False),
    ("users", "consent_given_at", True),
]


def upgrade() -> None:
    for table, column, nullable in _DATETIME_COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            existing_type=sa.String(),
            existing_nullable=nullable,
            postgresql_using=f"{column}::timestamptz",
        )


def downgrade() -> None:
    for table, column, nullable in reversed(_DATETIME_COLUMNS):
        op.alter_column(
            table,
            column,
            type_=sa.String(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=nullable,
        )
