"""FMCG optional manufacturing: recipes, production orders, materials, trace, overheads.

Revision ID: 20261120_0222f
Revises: 20261120_0221f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0222f"
down_revision = "20261120_0221f"
branch_labels = None
depends_on = None


def _fk(name: str):
    return sa.ForeignKey(name)


def _tenant():
    return sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True)


def upgrade() -> None:
    op.create_table(
        "fmcg_boms",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("output_qty", sa.Numeric(14, 3), nullable=False, server_default="1"),
        sa.Column("shelf_life_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "fmcg_bom_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("bom_id", sa.String(36), _fk("fmcg_boms.id"), nullable=False, index=True),
        sa.Column("component_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("wastage_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
    )
    op.create_table(
        "fmcg_production_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("order_number", sa.String(40), nullable=False),
        sa.Column("bom_id", sa.String(36), _fk("fmcg_boms.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("planned_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("produced_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column("status", sa.String(14), nullable=False, index=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("batch_number", sa.String(80), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("held_for_qc", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("material_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("overhead_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("cancel_reason", sa.String(255), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_fmcg_production_number"),
    )
    op.create_table(
        "fmcg_production_materials",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("order_id", sa.String(36), _fk("fmcg_production_orders.id"), nullable=False, index=True),
        sa.Column("component_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("standard_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("actual_qty", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4), nullable=False),
    )
    op.create_table(
        "fmcg_production_trace",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("order_id", sa.String(36), _fk("fmcg_production_orders.id"), nullable=False, index=True),
        sa.Column("component_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), _fk("product_batches.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
    )
    op.create_table(
        "fmcg_production_overheads",
        sa.Column("id", sa.String(36), primary_key=True),
        _tenant(),
        sa.Column("order_id", sa.String(36), _fk("fmcg_production_orders.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("pay_method", sa.String(16), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    for t in ("fmcg_production_overheads", "fmcg_production_trace", "fmcg_production_materials", "fmcg_production_orders", "fmcg_bom_lines", "fmcg_boms"):
        op.drop_table(t)
