"""FMCG import shipments and landed cost.

Revision ID: 20261120_0221f
Revises: 20261120_0220f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0221f"
down_revision = "20261120_0220f"
branch_labels = None
depends_on = None


def _fk(name: str):
    return sa.ForeignKey(name)


def upgrade() -> None:
    op.create_table(
        "fmcg_shipments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("shipment_number", sa.String(40), nullable=False),
        sa.Column("reference", sa.String(80), nullable=True),
        sa.Column("container_no", sa.String(40), nullable=True),
        sa.Column("supplier_id", sa.String(36), _fk("parties.id"), nullable=True, index=True),
        sa.Column("grn_id", sa.String(36), _fk("goods_receipts.id"), nullable=True, index=True),
        sa.Column("eta", sa.Date(), nullable=True),
        sa.Column("basis", sa.String(10), nullable=False, server_default="value"),
        sa.Column("status", sa.String(12), nullable=False, server_default="open", index=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("total_costs", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("allocated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "shipment_number", name="uq_fmcg_shipment_number"),
    )
    op.create_table(
        "fmcg_shipment_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("shipment_id", sa.String(36), _fk("fmcg_shipments.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("goods_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("allocated", sa.Numeric(14, 2), nullable=True),
        sa.Column("capitalised", sa.Numeric(14, 2), nullable=True),
        sa.Column("cost_before", sa.Numeric(14, 4), nullable=True),
        sa.Column("cost_after", sa.Numeric(14, 4), nullable=True),
    )
    op.create_table(
        "fmcg_shipment_costs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("shipment_id", sa.String(36), _fk("fmcg_shipments.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("vendor", sa.String(120), nullable=True),
        sa.Column("pay_method", sa.String(16), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("fmcg_shipment_costs")
    op.drop_table("fmcg_shipment_lines")
    op.drop_table("fmcg_shipments")
