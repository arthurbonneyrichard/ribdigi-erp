"""expense workflow tables

Revision ID: 20260808_0006
Revises: 20260808_0005
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0006"
down_revision = "20260808_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("expense_approval_threshold", sa.Numeric(14, 2), nullable=False, server_default="100"),
    )

    op.create_table(
        "expense_categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("budget_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("tenant_id", "code"),
    )
    op.create_index("ix_expense_categories_tenant_id", "expense_categories", ["tenant_id"])

    op.add_column("expenses", sa.Column("category_id", sa.String(length=36), sa.ForeignKey("expense_categories.id"), nullable=True))
    op.add_column("expenses", sa.Column("expense_date", sa.DateTime(), nullable=True))
    op.add_column("expenses", sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"))
    op.add_column("expenses", sa.Column("reference", sa.String(length=100), nullable=True))
    op.add_column("expenses", sa.Column("payee", sa.String(length=150), nullable=True))
    op.add_column("expenses", sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True))
    op.add_column("expenses", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.add_column("expenses", sa.Column("approved_by", sa.String(length=36), nullable=True))
    op.add_column("expenses", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("expenses", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("expenses", sa.Column("approval_comment", sa.Text(), nullable=True))
    op.create_index("ix_expenses_status", "expenses", ["status"])

    op.execute("UPDATE expenses SET expense_date = created_at WHERE expense_date IS NULL")

    op.create_table(
        "recurring_expenses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("category_id", sa.String(length=36), sa.ForeignKey("expense_categories.id"), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("payee", sa.String(length=150), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=False),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_recurring_expenses_tenant_id", "recurring_expenses", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("recurring_expenses")
    op.drop_index("ix_expenses_status", table_name="expenses")
    for col in [
        "approval_comment",
        "rejection_reason",
        "approved_at",
        "approved_by",
        "created_by",
        "store_id",
        "payee",
        "reference",
        "payment_method",
        "expense_date",
        "category_id",
    ]:
        op.drop_column("expenses", col)
    op.drop_table("expense_categories")
    op.drop_column("tenants", "expense_approval_threshold")
