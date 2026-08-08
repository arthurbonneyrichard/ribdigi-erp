"""backup jobs and schedule settings

Revision ID: 20260808_0012
Revises: 20260808_0011
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0012"
down_revision = "20260808_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("filename", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("storage_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("record_counts", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_backup_jobs_tenant_id", "backup_jobs", ["tenant_id"])
    op.create_index("ix_backup_jobs_status", "backup_jobs", ["status"])

    op.create_table(
        "backup_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="daily"),
        sa.Column("retention_count", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("hour_utc", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_backup_settings_tenant_id", "backup_settings", ["tenant_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_backup_settings_tenant_id", table_name="backup_settings")
    op.drop_table("backup_settings")
    op.drop_index("ix_backup_jobs_status", table_name="backup_jobs")
    op.drop_index("ix_backup_jobs_tenant_id", table_name="backup_jobs")
    op.drop_table("backup_jobs")
