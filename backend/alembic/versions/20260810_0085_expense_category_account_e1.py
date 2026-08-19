"""Expense category GL account link (Stage 14 E1)

Revision ID: 20260810_0085
Revises: 20260809_0084
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260810_0085"
down_revision = "20260809_0084"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("expense_categories") as batch:
        batch.add_column(
            sa.Column(
                "account_id",
                sa.String(length=36),
                sa.ForeignKey("accounts.id"),
                nullable=True,
            )
        )
        batch.create_index("ix_expense_categories_account_id", ["account_id"])


def downgrade() -> None:
    with op.batch_alter_table("expense_categories") as batch:
        batch.drop_index("ix_expense_categories_account_id")
        batch.drop_column("account_id")
