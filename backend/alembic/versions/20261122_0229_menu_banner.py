"""Digital menu banner image (top or footer of the guest menu).

Revision ID: 20261122_0229
Revises: 20261121_0228f
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_0229"
down_revision = "20261121_0228f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_menu_settings", sa.Column("banner_url", sa.String(500), nullable=True))
    op.add_column(
        "restaurant_menu_settings",
        sa.Column("banner_position", sa.String(10), nullable=False, server_default="top"),
    )


def downgrade() -> None:
    op.drop_column("restaurant_menu_settings", "banner_position")
    op.drop_column("restaurant_menu_settings", "banner_url")
