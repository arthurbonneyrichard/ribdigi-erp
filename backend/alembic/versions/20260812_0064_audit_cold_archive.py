"""Audit cold archive metadata + archived_at (BR-17.2)

Revision ID: 20260812_0064
Revises: 20260812_0063
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0064"
down_revision = "20260812_0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.create_index("ix_audit_logs_archived_at", "audit_logs", ["archived_at"])

    op.create_table(
        "audit_cold_archives",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(length=36),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("from_created_at", sa.DateTime(), nullable=True),
        sa.Column("to_created_at", sa.DateTime(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_cold_archives_tenant_id", "audit_cold_archives", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_cold_archives_tenant_id", table_name="audit_cold_archives")
    op.drop_table("audit_cold_archives")
    op.drop_index("ix_audit_logs_archived_at", table_name="audit_logs")
    op.drop_column("audit_logs", "archived_at")
