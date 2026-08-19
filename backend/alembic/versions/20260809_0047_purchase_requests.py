"""Purchase requests

Revision ID: 20260809_0047
Revises: 20260809_0046
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0047"
down_revision = "20260809_0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("request_number", sa.String(length=50), nullable=False),
        sa.Column("supplier_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(length=36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("required_date", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "purchase_order_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_orders.id"),
            nullable=True,
        ),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "request_number"),
    )
    op.create_index("ix_purchase_requests_tenant_id", "purchase_requests", ["tenant_id"])
    op.create_index("ix_purchase_requests_request_number", "purchase_requests", ["request_number"])
    op.create_index("ix_purchase_requests_supplier_id", "purchase_requests", ["supplier_id"])
    op.create_index("ix_purchase_requests_status", "purchase_requests", ["status"])
    op.create_index("ix_purchase_requests_purchase_order_id", "purchase_requests", ["purchase_order_id"])

    op.create_table(
        "purchase_request_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "purchase_request_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_requests.id"),
            nullable=False,
        ),
        sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_purchase_request_items_tenant_id", "purchase_request_items", ["tenant_id"])
    op.create_index(
        "ix_purchase_request_items_purchase_request_id",
        "purchase_request_items",
        ["purchase_request_id"],
    )
    op.create_index("ix_purchase_request_items_product_id", "purchase_request_items", ["product_id"])

    op.add_column(
        "purchase_orders",
        sa.Column("purchase_request_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        "ix_purchase_orders_purchase_request_id",
        "purchase_orders",
        ["purchase_request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_purchase_orders_purchase_request_id", table_name="purchase_orders")
    op.drop_column("purchase_orders", "purchase_request_id")
    op.drop_table("purchase_request_items")
    op.drop_table("purchase_requests")
