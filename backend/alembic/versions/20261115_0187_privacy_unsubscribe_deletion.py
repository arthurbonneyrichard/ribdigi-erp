"""Marketing email unsubscribe list and data deletion requests.

Revision ID: 20261115_0187
Revises: 20261115_0184
Create Date: 2026-11-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261115_0187"
down_revision = "20261115_0184"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_suppressions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False, server_default="marketing"),
        sa.Column("source", sa.String(30), nullable=False, server_default="link"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email", "scope", name="uq_email_suppressions_email_scope"),
    )
    op.create_index("ix_email_suppressions_email", "email_suppressions", ["email"])
    op.create_table(
        "data_deletion_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("requester_email", sa.String(255), nullable=True),
        sa.Column("requester_name", sa.String(150), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_data_deletion_requests_tenant_id", "data_deletion_requests", ["tenant_id"])
    op.create_index("ix_data_deletion_requests_status", "data_deletion_requests", ["status"])


def downgrade() -> None:
    op.drop_index("ix_data_deletion_requests_status", table_name="data_deletion_requests")
    op.drop_index("ix_data_deletion_requests_tenant_id", table_name="data_deletion_requests")
    op.drop_table("data_deletion_requests")
    op.drop_index("ix_email_suppressions_email", table_name="email_suppressions")
    op.drop_table("email_suppressions")
