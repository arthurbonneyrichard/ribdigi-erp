"""Expense org dimensions store/department (Stage 14 E2)

Revision ID: 20260810_0086
Revises: 20260810_0085
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = "20260810_0086"
down_revision = "20260810_0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("expenses") as batch:
        batch.add_column(
            sa.Column(
                "department_id",
                sa.String(length=36),
                sa.ForeignKey("departments.id"),
                nullable=True,
            )
        )
        batch.create_index("ix_expenses_department_id", ["department_id"])

    with op.batch_alter_table("recurring_expenses") as batch:
        batch.add_column(
            sa.Column(
                "store_id",
                sa.String(length=36),
                sa.ForeignKey("stores.id"),
                nullable=True,
            )
        )
        batch.add_column(
            sa.Column(
                "department_id",
                sa.String(length=36),
                sa.ForeignKey("departments.id"),
                nullable=True,
            )
        )
        batch.create_index("ix_recurring_expenses_store_id", ["store_id"])
        batch.create_index("ix_recurring_expenses_department_id", ["department_id"])


def downgrade() -> None:
    with op.batch_alter_table("recurring_expenses") as batch:
        batch.drop_index("ix_recurring_expenses_department_id")
        batch.drop_index("ix_recurring_expenses_store_id")
        batch.drop_column("department_id")
        batch.drop_column("store_id")
    with op.batch_alter_table("expenses") as batch:
        batch.drop_index("ix_expenses_department_id")
        batch.drop_column("department_id")
