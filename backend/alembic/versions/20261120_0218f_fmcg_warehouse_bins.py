"""FMCG warehouse zones, bins, bin stock and bin counts.

Revision ID: 20261120_0218f
Revises: 20261120_0217f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0218f"
down_revision = "20261120_0217f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_locations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False, index=True),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("fmcg_locations.id"), nullable=True, index=True),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("zone_type", sa.String(20), nullable=True),
        sa.Column("capacity", sa.Numeric(14, 3), nullable=True),
        sa.Column("pick_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "warehouse_id", "code", name="uq_fmcg_location_code"),
    )
    op.create_table(
        "fmcg_bin_stock",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("bin_id", sa.String(36), sa.ForeignKey("fmcg_locations.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("product_batches.id"), nullable=True, index=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "fmcg_bin_counts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("bin_id", sa.String(36), sa.ForeignKey("fmcg_locations.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), nullable=True),
        sa.Column("expected_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("counted_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("variance_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("counted_by", sa.String(36), nullable=True),
        sa.Column("counted_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("fmcg_bin_counts")
    op.drop_table("fmcg_bin_stock")
    op.drop_table("fmcg_locations")
