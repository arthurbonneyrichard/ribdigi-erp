"""Add warehouse type, manager, address, capacity (BR-2.4).

Revision ID: 20260813_0082
Revises: 20260813_0081
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260813_0082"
down_revision = "20260813_0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "warehouses",
        sa.Column("warehouse_type", sa.String(length=32), nullable=False, server_default="retail"),
    )
    op.add_column(
        "warehouses",
        sa.Column("manager_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("warehouses", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("warehouses", sa.Column("capacity", sa.Numeric(14, 3), nullable=True))


def downgrade() -> None:
    op.drop_column("warehouses", "capacity")
    op.drop_column("warehouses", "address")
    op.drop_column("warehouses", "manager_id")
    op.drop_column("warehouses", "warehouse_type")
