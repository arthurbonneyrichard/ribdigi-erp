"""FMCG distributors: trade terms on an outlet.

Revision ID: 20261120_0223f
Revises: 20261120_0222f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0223f"
down_revision = "20261120_0222f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fmcg_distributors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("parties.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(14), nullable=False, server_default="distributor"),
        sa.Column("price_discount_pct", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("monthly_target", sa.Numeric(14, 2), nullable=True),
        sa.Column("territory_id", sa.String(36), sa.ForeignKey("fmcg_territories.id"), nullable=True, index=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "customer_id", name="uq_fmcg_distributor_customer"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_distributors")
