"""Document line alternate UoM (BR-5.1 follow-through).

Revision ID: 20260812_0074
Revises: 20260812_0073
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0074"
down_revision = "20260812_0073"
branch_labels = None
depends_on = None

_TABLES = (
    "purchase_order_items",
    "goods_receipt_items",
    "sales_invoice_items",
    "sales_order_items",
    "sales_quotation_items",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("unit_id", sa.String(length=36), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_unit_id",
            table,
            "units_of_measure",
            ["unit_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_unit_id", table, ["unit_id"])


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_unit_id", table_name=table)
        op.drop_constraint(f"fk_{table}_unit_id", table, type_="foreignkey")
        op.drop_column(table, "unit_id")
