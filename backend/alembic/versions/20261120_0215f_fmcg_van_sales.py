"""FMCG van sales: van loads, van expenses, van closings.

Revision ID: 20261120_0215f
Revises: 20261120_0214f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0215f"
down_revision = "20261120_0214f"
branch_labels = None
depends_on = None


def _fk(name: str):
    return sa.ForeignKey(name)


def upgrade() -> None:
    op.create_table(
        "fmcg_van_loads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("dispatch_id", sa.String(36), _fk("fmcg_dispatches.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("loaded_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("sold_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("damaged_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("sample_qty", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("counted_qty", sa.Numeric(14, 3), nullable=True),
        sa.Column("variance_qty", sa.Numeric(14, 3), nullable=True),
        sa.UniqueConstraint("tenant_id", "dispatch_id", "product_id", name="uq_fmcg_van_load"),
    )
    op.create_table(
        "fmcg_van_expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("dispatch_id", sa.String(36), _fk("fmcg_dispatches.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("journal_entry_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "fmcg_van_closings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("dispatch_id", sa.String(36), _fk("fmcg_dispatches.id"), nullable=False, index=True),
        sa.Column("stock_variance_value", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("cash_variance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.String(36), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "dispatch_id", name="uq_fmcg_van_closing"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_van_closings")
    op.drop_table("fmcg_van_expenses")
    op.drop_table("fmcg_van_loads")
