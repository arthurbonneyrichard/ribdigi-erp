"""FMCG promotions: approval, budget, limits and eligibility.

Revision ID: 20261120_0217f
Revises: 20261120_0216f
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261120_0217f"
down_revision = "20261120_0216f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing schemes keep working: they are approved.
    op.add_column("fmcg_trade_schemes", sa.Column("status", sa.String(20), nullable=False, server_default="approved"))
    op.create_index("ix_fmcg_trade_schemes_status", "fmcg_trade_schemes", ["status"])
    op.add_column("fmcg_trade_schemes", sa.Column("budget", sa.Numeric(14, 2), nullable=True))
    op.add_column("fmcg_trade_schemes", sa.Column("max_uses", sa.Integer(), nullable=True))
    op.add_column("fmcg_trade_schemes", sa.Column("min_qty", sa.Numeric(14, 3), nullable=True))
    op.add_column("fmcg_trade_schemes", sa.Column("created_by", sa.String(36), nullable=True))
    op.add_column("fmcg_trade_schemes", sa.Column("approved_by", sa.String(36), nullable=True))
    op.add_column("fmcg_trade_schemes", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("fmcg_trade_schemes", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.create_table(
        "fmcg_scheme_targets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("scheme_id", sa.String(36), sa.ForeignKey("fmcg_trade_schemes.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("ref_id", sa.String(36), nullable=False, index=True),
        sa.UniqueConstraint("tenant_id", "scheme_id", "kind", "ref_id", name="uq_fmcg_scheme_target"),
    )


def downgrade() -> None:
    op.drop_table("fmcg_scheme_targets")
    for col in ("rejection_reason", "approved_at", "approved_by", "created_by", "min_qty", "max_uses", "budget"):
        op.drop_column("fmcg_trade_schemes", col)
    op.drop_index("ix_fmcg_trade_schemes_status", table_name="fmcg_trade_schemes")
    op.drop_column("fmcg_trade_schemes", "status")
