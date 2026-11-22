"""Gym trainer commissions.

Revision ID: 20261119_0208g
Revises: 20261119_0207g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0208g"
down_revision = "20261119_0207g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gym_trainers", sa.Column("commission_pct", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.create_table(
        "gym_commissions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("trainer_id", sa.String(36), sa.ForeignKey("gym_trainers.id"), nullable=False, index=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("gym_training_sessions.id"), nullable=False, index=True),
        sa.Column("session_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("earned_on", sa.Date(), nullable=False, index=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="accrued", index=True),
        sa.Column("paid_on", sa.Date()), sa.Column("pay_reference", sa.String(100)), sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("session_id", name="uq_gym_commission_session"),
    )


def downgrade() -> None:
    op.drop_table("gym_commissions")
    op.drop_column("gym_trainers", "commission_pct")
