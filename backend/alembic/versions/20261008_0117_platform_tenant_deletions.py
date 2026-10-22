"""Platform record of a completed or failed company deletion.

Revision ID: 20261008_0117
Revises: 20261006_0116
Create Date: 2026-10-08

The table has no tenant foreign key and no company name. Tenant purge
deletes every table that has tenant_id, so this row remains.
"""

from alembic import op
import sqlalchemy as sa

revision = "20261008_0117"
down_revision = "20261006_0116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_tenant_deletions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_tenant_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=40), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_platform_tenant_deletions_deleted_tenant_id",
        "platform_tenant_deletions",
        ["deleted_tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_platform_tenant_deletions_deleted_tenant_id",
        table_name="platform_tenant_deletions",
    )
    op.drop_table("platform_tenant_deletions")
