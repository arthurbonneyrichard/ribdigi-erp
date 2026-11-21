"""Gym equipment: purchase details for depreciation.

Revision ID: 20261119_0212g
Revises: 20261119_0211g
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0212g"
down_revision = "20261119_0211g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gym_equipment", sa.Column("purchase_date", sa.Date()))
    op.add_column("gym_equipment", sa.Column("purchase_cost", sa.Numeric(14, 2)))
    op.add_column("gym_equipment", sa.Column("useful_life_months", sa.Integer()))
    op.add_column("gym_equipment", sa.Column("warranty_until", sa.Date()))
    op.add_column("gym_equipment", sa.Column("supplier_name", sa.String(150)))


def downgrade() -> None:
    for c in ("supplier_name", "warranty_until", "useful_life_months", "purchase_cost", "purchase_date"):
        op.drop_column("gym_equipment", c)
