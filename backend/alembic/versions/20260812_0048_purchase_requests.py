"""Purchase requests and line items

Revision ID: 20260812_0048
Revises: 20260812_0047
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0048"
down_revision = "20260812_0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("request_number", sa.String(length=50), nullable=False, index=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column(
            "preferred_supplier_id",
            sa.String(length=36),
            sa.ForeignKey("parties.id"),
            nullable=True,
        ),
        sa.Column(
            "warehouse_id",
            sa.String(length=36),
            sa.ForeignKey("warehouses.id"),
            nullable=True,
        ),
        sa.Column("required_date", sa.DateTime(), nullable=True),
        sa.Column("department", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("rejected_by", sa.String(length=36), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "converted_po_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_orders.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "request_number"),
    )
    op.create_table(
        "purchase_request_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "purchase_request_id",
            sa.String(length=36),
            sa.ForeignKey("purchase_requests.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "variant_id",
            sa.String(length=36),
            sa.ForeignKey("product_variants.id"),
            nullable=True,
        ),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("purchase_request_items")
    op.drop_table("purchase_requests")
