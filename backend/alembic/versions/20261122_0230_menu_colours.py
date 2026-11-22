"""Digital menu: restaurant's own header and background colours.

Revision ID: 20261122_0230
Revises: 20261122_0229
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_0230"
down_revision = "20261122_0229"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_menu_settings", sa.Column("primary_color", sa.String(7), nullable=True))
    op.add_column("restaurant_menu_settings", sa.Column("background_color", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("restaurant_menu_settings", "background_color")
    op.drop_column("restaurant_menu_settings", "primary_color")
