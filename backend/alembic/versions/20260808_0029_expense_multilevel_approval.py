"""multi-level expense approval

Revision ID: 20260808_0029
Revises: 20260808_0028
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0029"
down_revision = "20260808_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "expense_l2_threshold",
            sa.Numeric(14, 2),
            nullable=False,
            server_default="1000",
        ),
    )
    op.add_column(
        "expenses",
        sa.Column("approval_step", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "expenses",
        sa.Column("approval_steps_required", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "expense_approval_actions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("expense_id", sa.String(length=36), sa.ForeignKey("expenses.id"), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_expense_approval_actions_tenant_id", "expense_approval_actions", ["tenant_id"])
    op.create_index("ix_expense_approval_actions_expense_id", "expense_approval_actions", ["expense_id"])


def downgrade() -> None:
    op.drop_index("ix_expense_approval_actions_expense_id", table_name="expense_approval_actions")
    op.drop_index("ix_expense_approval_actions_tenant_id", table_name="expense_approval_actions")
    op.drop_table("expense_approval_actions")
    op.drop_column("expenses", "approval_steps_required")
    op.drop_column("expenses", "approval_step")
    op.drop_column("tenants", "expense_l2_threshold")
