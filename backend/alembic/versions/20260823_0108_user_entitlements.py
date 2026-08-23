"""Tenant max_users_override for plan-synced user entitlement.

Revision ID: 20260823_0108
Revises: 20260823_0107
Create Date: 2026-08-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260823_0108"
down_revision = "20260823_0107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("max_users_override", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "max_users_override")
