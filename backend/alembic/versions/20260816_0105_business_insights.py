"""Smart Business Intelligence tables (Layer 1).

Revision ID: 20260816_0105
Revises: 20260816_0104
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260816_0105"
down_revision = "20260816_0104"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_insights",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("branch_id", sa.String(length=36), nullable=True),
        sa.Column("insight_type", sa.String(length=60), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=True),
        sa.Column("metric_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("comparison_value", sa.Numeric(18, 4), nullable=True),
        sa.Column("percentage_change", sa.Numeric(12, 4), nullable=True),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", sa.String(length=36), nullable=True),
        sa.Column("action_href", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_business_insights_tenant_id", "business_insights", ["tenant_id"])
    op.create_index("ix_business_insights_company_id", "business_insights", ["company_id"])
    op.create_index("ix_business_insights_priority", "business_insights", ["priority"])
    op.create_index("ix_business_insights_status", "business_insights", ["status"])
    op.create_index("ix_business_insights_created_at", "business_insights", ["created_at"])
    op.create_index(
        "ix_business_insights_type_status",
        "business_insights",
        ["tenant_id", "insight_type", "status"],
    )

    op.create_table(
        "business_insight_settings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("company_id", sa.String(length=36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "company_id", name="uq_bi_settings_tenant_company"),
    )
    op.create_index(
        "ix_business_insight_settings_tenant_id", "business_insight_settings", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_table("business_insight_settings")
    op.drop_table("business_insights")
