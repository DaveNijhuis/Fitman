"""add scale_user_id to users

Revision ID: j6k8l0m2n4o5
Revises: i5j7k9l1m3n4
Create Date: 2026-09-21

Adds scale_user_id: the user's id on the smart scale (#323), 4 random bytes
stored as 8 hex characters, unique, created on the first weigh-in. Nullable:
most users never use the scale (#326).

The constraint name matches what create_all produces for unique=True on
PostgreSQL, so migrated and freshly built databases agree.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "j6k8l0m2n4o5"
down_revision: Union[str, None] = "i5j7k9l1m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("scale_user_id", sa.String(length=8), nullable=True))
    op.create_unique_constraint("users_scale_user_id_key", "users", ["scale_user_id"])


def downgrade() -> None:
    op.drop_constraint("users_scale_user_id_key", "users", type_="unique")
    op.drop_column("users", "scale_user_id")
