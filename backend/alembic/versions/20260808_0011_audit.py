"""audit log integrity fields

Revision ID: 20260808_0011
Revises: 20260808_0010
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0011"
down_revision = "20260808_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("module", sa.String(length=40), nullable=False, server_default="system"),
    )
    op.add_column("audit_logs", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(length=255), nullable=True))
    op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("integrity_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_audit_logs_module", "audit_logs", ["module"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_integrity_hash", "audit_logs", ["integrity_hash"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_integrity_hash", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_module", table_name="audit_logs")
    op.drop_column("audit_logs", "integrity_hash")
    op.drop_column("audit_logs", "prev_hash")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "ip_address")
    op.drop_column("audit_logs", "module")
