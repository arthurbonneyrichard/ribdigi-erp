"""Storefront logo, banner, and favicon columns.

Revision ID: 20261021_0141
Revises: 20261021_0140
Create Date: 2026-10-21

Additive only. Do not apply to live ribdigi_erp from this work.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261021_0141"
down_revision = "20261021_0140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ecommerce_storefronts", sa.Column("logo_url", sa.String(500), nullable=True))
    op.add_column("ecommerce_storefronts", sa.Column("banner_url", sa.String(500), nullable=True))
    op.add_column("ecommerce_storefronts", sa.Column("favicon_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("ecommerce_storefronts", "favicon_url")
    op.drop_column("ecommerce_storefronts", "banner_url")
    op.drop_column("ecommerce_storefronts", "logo_url")
