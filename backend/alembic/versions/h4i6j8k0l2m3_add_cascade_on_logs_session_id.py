"""add ON DELETE CASCADE to logs.session_id FK

Revision ID: h4i6j8k0l2m3
Revises: g3h5i7j9k1l2
Create Date: 2026-07-12

logs.session_id references workout_sessions.id with no ondelete rule.
When a user is deleted, the DB cascades users → workout_sessions
(via the user_id CASCADE added in g3h5i7j9k1l2), but then fails with
a ForeignKeyViolation because logs.session_id has no CASCADE.

The application code in admin.py and gdpr.py worked around this by
manually deleting logs before deleting workout_sessions. After removing
that dead code (issue #221), the DB-level cascade must cover the full
chain: users → workout_sessions → logs.

This migration drops and recreates the logs_session_id_fkey constraint
with ON DELETE CASCADE so that deleting a workout_session automatically
removes all its logs, and deleting a user cascades cleanly all the way
through to logs without any application-level intervention.
"""

from alembic import op


def upgrade() -> None:
    op.drop_constraint("logs_session_id_fkey", "logs", type_="foreignkey")
    op.create_foreign_key(
        "logs_session_id_fkey",
        "logs",
        "workout_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("logs_session_id_fkey", "logs", type_="foreignkey")
    op.create_foreign_key(
        "logs_session_id_fkey",
        "logs",
        "workout_sessions",
        ["session_id"],
        ["id"],
    )
