"""HRM approval cover (delegation) and leave escalation.

Revision ID: 20261113_0177
Revises: 20261113_0176
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0177"
down_revision = "20261113_0176"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hrm_delegations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("from_employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("to_employee_id", sa.String(36), sa.ForeignKey("hrm_employees.id"), nullable=False, index=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("hrm_settings") as batch:
        batch.add_column(sa.Column("escalate_after_days", sa.Integer(), nullable=False, server_default="3"))
    with op.batch_alter_table("hrm_leave_requests") as batch:
        batch.add_column(sa.Column("escalated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hrm_leave_requests") as batch:
        batch.drop_column("escalated_at")
    with op.batch_alter_table("hrm_settings") as batch:
        batch.drop_column("escalate_after_days")
    op.drop_table("hrm_delegations")
