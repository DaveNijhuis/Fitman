"""add indexes on logs and body_measurements

Revision ID: e2f9a3b7c1d5
Revises: d5e8f2a1b4c7
Create Date: 2026-07-05

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e2f9a3b7c1d5"
down_revision: Union[str, Sequence[str], None] = "d5e8f2a1b4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_logs_session_id", "logs", ["session_id"])
    op.create_index("ix_logs_exercise_id", "logs", ["exercise_id"])
    op.create_index("ix_workout_sessions_user_id", "workout_sessions", ["user_id"])
    op.create_index("ix_body_measurements_user_id", "body_measurements", ["user_id"])
    op.create_index("ix_cardio_entries_user_id", "cardio_entries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_logs_session_id", table_name="logs")
    op.drop_index("ix_logs_exercise_id", table_name="logs")
    op.drop_index("ix_workout_sessions_user_id", table_name="workout_sessions")
    op.drop_index("ix_body_measurements_user_id", table_name="body_measurements")
    op.drop_index("ix_cardio_entries_user_id", table_name="cardio_entries")
