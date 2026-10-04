"""Add branch/department on expenses (BR-9.2).

Revision ID: 20260813_0091
Revises: 20260813_0090
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0091"
down_revision = "20260813_0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("branch_id", sa.String(length=36), nullable=True))
    op.add_column("expenses", sa.Column("department_id", sa.String(length=36), nullable=True))
    op.create_foreign_key("fk_expenses_branch_id", "expenses", "branches", ["branch_id"], ["id"])
    op.create_foreign_key(
        "fk_expenses_department_id", "expenses", "departments", ["department_id"], ["id"]
    )
    op.create_index("ix_expenses_branch_id", "expenses", ["branch_id"])
    op.create_index("ix_expenses_department_id", "expenses", ["department_id"])

    op.add_column("recurring_expenses", sa.Column("branch_id", sa.String(length=36), nullable=True))
    op.add_column(
        "recurring_expenses", sa.Column("department_id", sa.String(length=36), nullable=True)
    )
    op.create_foreign_key(
        "fk_recurring_expenses_branch_id",
        "recurring_expenses",
        "branches",
        ["branch_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_recurring_expenses_department_id",
        "recurring_expenses",
        "departments",
        ["department_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_recurring_expenses_department_id", "recurring_expenses", type_="foreignkey")
    op.drop_constraint("fk_recurring_expenses_branch_id", "recurring_expenses", type_="foreignkey")
    op.drop_column("recurring_expenses", "department_id")
    op.drop_column("recurring_expenses", "branch_id")

    op.drop_index("ix_expenses_department_id", table_name="expenses")
    op.drop_index("ix_expenses_branch_id", table_name="expenses")
    op.drop_constraint("fk_expenses_department_id", "expenses", type_="foreignkey")
    op.drop_constraint("fk_expenses_branch_id", "expenses", type_="foreignkey")
    op.drop_column("expenses", "department_id")
    op.drop_column("expenses", "branch_id")
