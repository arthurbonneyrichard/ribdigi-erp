"""sales return credit note + settlement fields

Revision ID: 20260812_0058
Revises: 20260812_0057
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0058"
down_revision = "20260812_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_returns", sa.Column("credit_note_number", sa.String(length=50), nullable=True))
    op.add_column("sales_returns", sa.Column("settlement_method", sa.String(length=20), nullable=True))
    op.add_column("sales_returns", sa.Column("refund_payment_method", sa.String(length=30), nullable=True))
    op.add_column("sales_returns", sa.Column("refund_liquid_account_id", sa.String(length=36), nullable=True))
    op.add_column(
        "sales_returns",
        sa.Column("refunded_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
    )
    op.create_index("ix_sales_returns_credit_note_number", "sales_returns", ["credit_note_number"])
    op.create_unique_constraint(
        "uq_sales_returns_tenant_credit_note",
        "sales_returns",
        ["tenant_id", "credit_note_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_sales_returns_tenant_credit_note", "sales_returns", type_="unique")
    op.drop_index("ix_sales_returns_credit_note_number", table_name="sales_returns")
    op.drop_column("sales_returns", "refunded_amount")
    op.drop_column("sales_returns", "refund_liquid_account_id")
    op.drop_column("sales_returns", "refund_payment_method")
    op.drop_column("sales_returns", "settlement_method")
    op.drop_column("sales_returns", "credit_note_number")
