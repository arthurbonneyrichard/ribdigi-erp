"""Digital menu: separate TV board background colour.

Revision ID: 20261122_0231
Revises: 20261122_0230
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_0231"
down_revision = "20261122_0230"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_menu_settings", sa.Column("board_background_color", sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column("restaurant_menu_settings", "board_background_color")
