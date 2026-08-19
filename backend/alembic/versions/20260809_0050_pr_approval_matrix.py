"""Purchase request multi-level approval matrix

Revision ID: 20260809_0050
Revises: 20260809_0049
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0050"
down_revision = "20260809_0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("purchase_request_approval_matrix", sa.JSON(), nullable=True),
    )
    op.add_column(
        "purchase_requests",
        sa.Column("estimated_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "purchase_requests",
        sa.Column("approval_step", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "purchase_requests",
        sa.Column("approval_steps_required", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "purchase_request_approval_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "purchase_request_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_requests.id"),
            nullable=False,
        ),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_purchase_request_approval_actions_tenant_id",
        "purchase_request_approval_actions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_purchase_request_approval_actions_purchase_request_id",
        "purchase_request_approval_actions",
        ["purchase_request_id"],
    )


def downgrade() -> None:
    op.drop_table("purchase_request_approval_actions")
    op.drop_column("purchase_requests", "approval_steps_required")
    op.drop_column("purchase_requests", "approval_step")
    op.drop_column("purchase_requests", "estimated_total")
    op.drop_column("tenants", "purchase_request_approval_matrix")
