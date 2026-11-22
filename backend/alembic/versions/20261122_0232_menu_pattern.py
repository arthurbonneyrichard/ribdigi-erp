"""Digital menu: background pattern (food icons, dots or none).

Revision ID: 20261122_0232
Revises: 20261122_0231
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_0232"
down_revision = "20261122_0231"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "restaurant_menu_settings",
        sa.Column("background_pattern", sa.String(10), nullable=False, server_default="food"),
    )


def downgrade() -> None:
    op.drop_column("restaurant_menu_settings", "background_pattern")
