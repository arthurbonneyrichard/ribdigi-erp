"""Optional purchase_invoices.warehouse_id for store-manager scope.

Revision ID: 20260823_0109
Revises: 20260823_0108
Create Date: 2026-08-23

Nullable FK — does not claim store-scoped RBAC Complete or ADR-005.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260823_0109"
down_revision = "20260823_0108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "purchase_invoices",
        sa.Column(
            "warehouse_id",
            sa.String(length=36),
            sa.ForeignKey("warehouses.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_purchase_invoices_warehouse_id",
        "purchase_invoices",
        ["warehouse_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_invoices_warehouse_id", table_name="purchase_invoices")
    op.drop_column("purchase_invoices", "warehouse_id")
