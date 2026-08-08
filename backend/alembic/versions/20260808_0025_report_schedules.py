"""report email schedules

Revision ID: 20260808_0025
Revises: 20260808_0024
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0025"
down_revision = "20260808_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("report_type", sa.String(length=60), nullable=False),
        sa.Column("format", sa.String(length=10), nullable=False, server_default="xlsx"),
        sa.Column("frequency", sa.String(length=20), nullable=False, server_default="daily"),
        sa.Column("weekday", sa.Integer(), nullable=True),
        sa.Column("hour_utc", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("recipients", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_report_schedules_tenant_id", "report_schedules", ["tenant_id"])
    op.create_index("ix_report_schedules_report_type", "report_schedules", ["report_type"])


def downgrade() -> None:
    op.drop_index("ix_report_schedules_report_type", table_name="report_schedules")
    op.drop_index("ix_report_schedules_tenant_id", table_name="report_schedules")
    op.drop_table("report_schedules")
