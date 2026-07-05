"""add consent_given_at to users

Revision ID: d5e8f2a1b4c7
Revises: c4a7b2e5f1d9
Create Date: 2026-07-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e8f2a1b4c7"
down_revision: Union[str, Sequence[str], None] = "c4a7b2e5f1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("consent_given_at", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("consent_given_at")
