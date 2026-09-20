"""add token_version to users

Revision ID: i5j7k9l1m3n4
Revises: h4i6j8k0l2m3
Create Date: 2026-07-12

Adds token_version (integer, default 1) to the users table so that
JWTs can be invalidated server-side without waiting for expiry.

When a user changes their password, token_version is incremented.
The JWT encodes the version at issue time; get_current_user rejects
any token whose version does not match the current DB value.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "i5j7k9l1m3n4"
down_revision: Union[str, None] = "h4i6j8k0l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")
