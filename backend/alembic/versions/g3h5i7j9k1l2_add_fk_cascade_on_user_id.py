"""add ON DELETE CASCADE to user_id FK constraints

Revision ID: g3h5i7j9k1l2
Revises: f1a2b3c4d5e6
Create Date: 2026-07-12

Migration b3d7f9e1c4a2 added user_id columns to workout_sessions,
cardio_entries, and body_measurements as plain integers with no FK
constraint. This migration adds the FK references to users.id with
ON DELETE CASCADE so that deleting a user at the DB level automatically
removes all their data, matching the application-level cascade in the
admin delete endpoint.

If a FK without CASCADE already exists (e.g. from an environment where
create_all was run against an older model), it is dropped and recreated.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "g3h5i7j9k1l2"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ["workout_sessions", "cardio_entries", "body_measurements"]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _TABLES:
        existing = {fk["name"] for fk in inspector.get_foreign_keys(table)}
        fk_name = f"{table}_user_id_fkey"
        if fk_name in existing:
            op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table in _TABLES:
        existing = {fk["name"] for fk in inspector.get_foreign_keys(table)}
        fk_name = f"{table}_user_id_fkey"
        if fk_name in existing:
            op.drop_constraint(fk_name, table, type_="foreignkey")
        # Restore FK without CASCADE
        op.create_foreign_key(
            fk_name,
            table,
            "users",
            ["user_id"],
            ["id"],
        )
