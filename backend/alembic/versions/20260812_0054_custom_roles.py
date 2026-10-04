"""tenant custom roles

Revision ID: 20260812_0054
Revises: 20260812_0053
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0054"
down_revision = "20260812_0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "custom_roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("base_role", sa.String(length=50), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("record_scope", sa.String(length=20), nullable=False, server_default="own"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "key", name="uq_custom_roles_tenant_key"),
    )
    op.create_index("ix_custom_roles_tenant_id", "custom_roles", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_custom_roles_tenant_id", table_name="custom_roles")
    op.drop_table("custom_roles")
