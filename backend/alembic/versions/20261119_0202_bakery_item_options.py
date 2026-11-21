"""Bakery item options (size, flavour, filling) with extra prices.

Revision ID: 20261119_0202
Revises: 20261119_0201
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0202"
down_revision = "20261119_0201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bakery_item_settings", sa.Column("options", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("bakery_item_settings", "options")
