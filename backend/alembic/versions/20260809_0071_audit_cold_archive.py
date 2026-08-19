"""Audit cold archive metadata + archived_at (BR-17.2 / G20)

Revision ID: 20260809_0071
Revises: 20260809_0070
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0071"
down_revision = "20260809_0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_audit_logs_archived_at", ["archived_at"])

    op.create_table(
        "audit_cold_archives",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("from_created_at", sa.DateTime(), nullable=True),
        sa.Column("to_created_at", sa.DateTime(), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_cold_archives")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_index("ix_audit_logs_archived_at")
        batch.drop_column("archived_at")
