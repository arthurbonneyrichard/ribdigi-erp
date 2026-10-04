"""AI report templates (BR-21.7).

Revision ID: 20260812_0069
Revises: 20260812_0068
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0069"
down_revision = "20260812_0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_report_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("report_type", sa.String(length=60), nullable=False),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("format", sa.String(length=10), nullable=False, server_default="csv"),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_ai_report_templates_tenant_name"),
    )
    op.create_index("ix_ai_report_templates_tenant_id", "ai_report_templates", ["tenant_id"])
    op.create_index("ix_ai_report_templates_report_type", "ai_report_templates", ["report_type"])


def downgrade() -> None:
    op.drop_index("ix_ai_report_templates_report_type", table_name="ai_report_templates")
    op.drop_index("ix_ai_report_templates_tenant_id", table_name="ai_report_templates")
    op.drop_table("ai_report_templates")
