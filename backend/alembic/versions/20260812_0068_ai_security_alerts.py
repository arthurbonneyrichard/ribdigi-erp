"""AI security alerts table (BR-21.10).

Revision ID: 20260812_0068
Revises: 20260812_0067
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0068"
down_revision = "20260812_0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_security_alerts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(length=60), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "fingerprint", name="uq_ai_security_alerts_tenant_fp"),
    )
    op.create_index("ix_ai_security_alerts_tenant_id", "ai_security_alerts", ["tenant_id"])
    op.create_index("ix_ai_security_alerts_kind", "ai_security_alerts", ["kind"])
    op.create_index("ix_ai_security_alerts_risk_score", "ai_security_alerts", ["risk_score"])
    op.create_index("ix_ai_security_alerts_user_id", "ai_security_alerts", ["user_id"])
    op.create_index("ix_ai_security_alerts_status", "ai_security_alerts", ["status"])
    op.create_index("ix_ai_security_alerts_created_at", "ai_security_alerts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_security_alerts_created_at", table_name="ai_security_alerts")
    op.drop_index("ix_ai_security_alerts_status", table_name="ai_security_alerts")
    op.drop_index("ix_ai_security_alerts_user_id", table_name="ai_security_alerts")
    op.drop_index("ix_ai_security_alerts_risk_score", table_name="ai_security_alerts")
    op.drop_index("ix_ai_security_alerts_kind", table_name="ai_security_alerts")
    op.drop_index("ix_ai_security_alerts_tenant_id", table_name="ai_security_alerts")
    op.drop_table("ai_security_alerts")
