"""Add GL account link on expense categories (BR-9.2).

Revision ID: 20260813_0092
Revises: 20260813_0091
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0092"
down_revision = "20260813_0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "expense_categories",
        sa.Column("account_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_expense_categories_account_id",
        "expense_categories",
        "accounts",
        ["account_id"],
        ["id"],
    )
    op.create_index("ix_expense_categories_account_id", "expense_categories", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_expense_categories_account_id", table_name="expense_categories")
    op.drop_constraint("fk_expense_categories_account_id", "expense_categories", type_="foreignkey")
    op.drop_column("expense_categories", "account_id")
