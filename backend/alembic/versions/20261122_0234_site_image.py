"""Restaurant website display image (the restaurant's own picture for the top of its site).

Revision ID: 20261122_0234
Revises: 20261122_0233
Create Date: 2026-11-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261122_0234"
down_revision = "20261122_0233"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("restaurant_menu_settings", sa.Column("site_image_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("restaurant_menu_settings", "site_image_url")
