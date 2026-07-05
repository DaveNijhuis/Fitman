"""merge heads and rename date_of_birth to birth_year

Revision ID: c4a7b2e5f1d9
Revises: b3d7f9e1c4a2, f6b436bab21e
Create Date: 2026-07-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a7b2e5f1d9"
down_revision: Union[str, Sequence[str], None] = ("b3d7f9e1c4a2", "f6b436bab21e")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("date_of_birth")
        batch_op.add_column(sa.Column("birth_year", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("birth_year")
        batch_op.add_column(sa.Column("date_of_birth", sa.String(), nullable=True))
