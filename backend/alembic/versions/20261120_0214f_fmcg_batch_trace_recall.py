"""FMCG: batch trace per delivered line, recalls.

Revision ID: 20261120_0214f
Revises: 20261120_0213g
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0214f"
down_revision = "20261120_0213g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_line_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("fmcg_orders.id"), nullable=False, index=True),
        sa.Column("order_line_id", sa.String(36), sa.ForeignKey("fmcg_order_lines.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("product_batches.id"), nullable=False, index=True),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("returned_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "fmcg_recalls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("recall_number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, index=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "recall_number", name="uq_fmcg_recall_number"),
    )
    op.create_table(
        "fmcg_recall_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("recall_id", sa.String(36), sa.ForeignKey("fmcg_recalls.id"), nullable=False, index=True),
        sa.Column("batch_id", sa.String(36), sa.ForeignKey("product_batches.id"), nullable=False, index=True),
        sa.Column("quantity_in_stock", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("quantity_delivered", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("recovered_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "recall_id", "batch_id", name="uq_fmcg_recall_batch"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_recall_batches")
    op.drop_table("fmcg_recalls")
    op.drop_table("fmcg_line_batches")
