"""Tenant custom roles for RBAC

Revision ID: 20260809_0053
Revises: 20260809_0052
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0053"
down_revision = "20260809_0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("record_scope", sa.String(length=20), nullable=False, server_default="own"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_custom_roles_tenant_slug"),
    )
    op.create_index("ix_custom_roles_tenant_id", "custom_roles", ["tenant_id"])
    op.create_index("ix_custom_roles_slug", "custom_roles", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_custom_roles_slug", table_name="custom_roles")
    op.drop_index("ix_custom_roles_tenant_id", table_name="custom_roles")
    op.drop_table("custom_roles")
