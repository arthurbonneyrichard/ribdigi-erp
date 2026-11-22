"""Restaurant website design (colours, font, corners, layout) kept with the menu settings.

Revision ID: 20261122_0233
Revises: 20261122_0232
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_0233"
down_revision = "20261122_0232"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_menu_settings", sa.Column("site_design", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("restaurant_menu_settings", "site_design")
