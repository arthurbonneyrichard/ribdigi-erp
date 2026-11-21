"""FMCG merchandising: must-stock list, shelf audits, competitor prices.

Revision ID: 20261120_0220f
Revises: 20261120_0219f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0220f"
down_revision = "20261120_0219f"
branch_labels = None
depends_on = None


def _fk(name: str):
    return sa.ForeignKey(name)


def upgrade() -> None:
    op.create_table(
        "fmcg_must_stock",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("min_facings", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("tenant_id", "product_id", name="uq_fmcg_must_stock"),
    )
    op.create_table(
        "fmcg_shelf_audits",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("outlet_id", sa.String(36), _fk("parties.id"), nullable=False, index=True),
        sa.Column("visit_id", sa.String(36), _fk("fmcg_visits.id"), nullable=True, index=True),
        sa.Column("auditor_id", sa.String(36), nullable=True, index=True),
        sa.Column("display_ok", sa.Boolean(), nullable=True),
        sa.Column("required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("compliant", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_pct", sa.Numeric(5, 1), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("photo", sa.Text(), nullable=True),
        sa.Column("audited_at", sa.DateTime(), nullable=False, index=True),
    )
    op.create_table(
        "fmcg_shelf_audit_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("audit_id", sa.String(36), _fk("fmcg_shelf_audits.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("present", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("facings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("shelf_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("must_stock", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_facings", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "fmcg_competitor_prices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), _fk("tenants.id"), nullable=False, index=True),
        sa.Column("outlet_id", sa.String(36), _fk("parties.id"), nullable=True, index=True),
        sa.Column("product_id", sa.String(36), _fk("products.id"), nullable=False, index=True),
        sa.Column("competitor_brand", sa.String(120), nullable=False),
        sa.Column("competitor_product", sa.String(160), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("observed_by", sa.String(36), nullable=True),
        sa.Column("observed_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("fmcg_competitor_prices")
    op.drop_table("fmcg_shelf_audit_lines")
    op.drop_table("fmcg_shelf_audits")
    op.drop_table("fmcg_must_stock")
