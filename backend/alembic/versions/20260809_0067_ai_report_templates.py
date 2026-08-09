"""ai_report_templates for BR-21.7 NL report generator

Revision ID: 20260809_0067
Revises: 20260809_0066
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0067"
down_revision = "20260809_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_report_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("report_type", sa.String(length=60), nullable=False, index=True),
        sa.Column("format", sa.String(length=10), nullable=False, server_default="xlsx"),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_report_templates")
