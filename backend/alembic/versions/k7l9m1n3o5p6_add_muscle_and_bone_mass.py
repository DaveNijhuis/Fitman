"""add muscle and bone mass to body_measurements

Revision ID: k7l9m1n3o5p6
Revises: j6k8l0m2n4o5
Create Date: 2026-09-22

Muscle mass and bone mass from iCOMON WLA25's derivation chain, as the
scale's own app shows them (#344). Nullable: manual weigh-ins without body fat
have neither, and the startup backfill fills rows derived before this.
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "k7l9m1n3o5p6"
down_revision: Union[str, None] = "j6k8l0m2n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("body_measurements", sa.Column("muscle_mass_kg", sa.Float(), nullable=True))
    op.add_column("body_measurements", sa.Column("bone_mass_kg", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("body_measurements", "bone_mass_kg")
    op.drop_column("body_measurements", "muscle_mass_kg")
