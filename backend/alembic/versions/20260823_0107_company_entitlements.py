"""Tenant max_companies_override for plan-synced company entitlement.

Revision ID: 20260823_0107
Revises: 20260823_0106
Create Date: 2026-08-23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260823_0107"
down_revision = "20260823_0106"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("max_companies_override", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "max_companies_override")
