"""ADR-005 user↔store membership table (scaffold — Complete still MISSING).

Revision ID: 20260914_0113
Revises: 20260914_0112
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260914_0113"
down_revision = "20260914_0112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_store_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "store_id",
            name="uq_user_store_memberships_tenant_user_store",
        ),
    )
    op.create_index(
        "ix_user_store_memberships_tenant_id",
        "user_store_memberships",
        ["tenant_id"],
    )
    op.create_index(
        "ix_user_store_memberships_company_id",
        "user_store_memberships",
        ["company_id"],
    )
    op.create_index(
        "ix_user_store_memberships_user_id",
        "user_store_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_user_store_memberships_store_id",
        "user_store_memberships",
        ["store_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_store_memberships_store_id", table_name="user_store_memberships")
    op.drop_index("ix_user_store_memberships_user_id", table_name="user_store_memberships")
    op.drop_index("ix_user_store_memberships_company_id", table_name="user_store_memberships")
    op.drop_index("ix_user_store_memberships_tenant_id", table_name="user_store_memberships")
    op.drop_table("user_store_memberships")
