"""AI queries audit table (secure packaging).

Revision ID: 20260812_0067
Revises: 20260812_0066
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0067"
down_revision = "20260812_0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_queries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("endpoint", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=64), nullable=True),
        sa.Column("prompt_preview", sa.String(length=120), nullable=True),
        sa.Column("message_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_reason", sa.String(length=80), nullable=True),
        sa.Column("insight_count", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_queries_tenant_id", "ai_queries", ["tenant_id"])
    op.create_index("ix_ai_queries_user_id", "ai_queries", ["user_id"])
    op.create_index("ix_ai_queries_endpoint", "ai_queries", ["endpoint"])
    op.create_index("ix_ai_queries_status", "ai_queries", ["status"])
    op.create_index("ix_ai_queries_prompt_sha256", "ai_queries", ["prompt_sha256"])
    op.create_index("ix_ai_queries_created_at", "ai_queries", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_queries_created_at", table_name="ai_queries")
    op.drop_index("ix_ai_queries_prompt_sha256", table_name="ai_queries")
    op.drop_index("ix_ai_queries_status", table_name="ai_queries")
    op.drop_index("ix_ai_queries_endpoint", table_name="ai_queries")
    op.drop_index("ix_ai_queries_user_id", table_name="ai_queries")
    op.drop_index("ix_ai_queries_tenant_id", table_name="ai_queries")
    op.drop_table("ai_queries")
