"""User store memberships for store-scoped RBAC.

Revision ID: 20260917_0105
Revises: 20260816_0105
Create Date: 2026-09-17

Idempotent: skip create when table/indexes already exist.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260917_0105"
down_revision = "20260816_0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "user_store_memberships" not in tables:
        op.create_table(
            "user_store_memberships",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("tenant_id", "user_id", "store_id"),
        )
        insp = sa.inspect(bind)

    existing_ix = {ix["name"] for ix in (insp.get_indexes("user_store_memberships") or []) if ix.get("name")}
    if "ix_user_store_memberships_tenant_id" not in existing_ix:
        op.create_index(
            "ix_user_store_memberships_tenant_id", "user_store_memberships", ["tenant_id"]
        )
    if "ix_user_store_memberships_user_id" not in existing_ix:
        op.create_index(
            "ix_user_store_memberships_user_id", "user_store_memberships", ["user_id"]
        )
    if "ix_user_store_memberships_store_id" not in existing_ix:
        op.create_index(
            "ix_user_store_memberships_store_id", "user_store_memberships", ["store_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "user_store_memberships" not in set(insp.get_table_names()):
        return
    existing_ix = {ix["name"] for ix in (insp.get_indexes("user_store_memberships") or []) if ix.get("name")}
    if "ix_user_store_memberships_store_id" in existing_ix:
        op.drop_index("ix_user_store_memberships_store_id", table_name="user_store_memberships")
    if "ix_user_store_memberships_user_id" in existing_ix:
        op.drop_index("ix_user_store_memberships_user_id", table_name="user_store_memberships")
    if "ix_user_store_memberships_tenant_id" in existing_ix:
        op.drop_index("ix_user_store_memberships_tenant_id", table_name="user_store_memberships")
    op.drop_table("user_store_memberships")
