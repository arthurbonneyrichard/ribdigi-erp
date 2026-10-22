"""Storefront shoppers, variant lines, and Woo outbound columns.

Revision ID: 20261021_0140
Revises: 20261021_0139
Create Date: 2026-10-21

Additive only. Do not apply to live ribdigi_erp from this work.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261021_0140"
down_revision = "20261021_0139"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ecommerce_shoppers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("party_id", sa.String(36), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("session_token", sa.String(80), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "email"),
        sa.UniqueConstraint("session_token"),
    )
    with op.batch_alter_table("ecommerce_cart_items") as batch:
        batch.add_column(sa.Column("variant_id", sa.String(36), sa.ForeignKey("product_variants.id"), nullable=True))
        batch.drop_constraint("ecommerce_cart_items_cart_id_product_id_key", type_="unique")
        batch.create_unique_constraint(
            "uq_ecommerce_cart_items_line",
            ["cart_id", "product_id", "variant_id"],
        )
    op.add_column(
        "ecommerce_order_items",
        sa.Column("variant_id", sa.String(36), sa.ForeignKey("product_variants.id"), nullable=True),
    )
    op.add_column(
        "ecommerce_reservations",
        sa.Column("variant_id", sa.String(36), sa.ForeignKey("product_variants.id"), nullable=True),
    )
    op.add_column(
        "ecommerce_orders",
        sa.Column("shopper_id", sa.String(36), sa.ForeignKey("ecommerce_shoppers.id"), nullable=True),
    )
    op.create_index("ix_ecommerce_orders_shopper_id", "ecommerce_orders", ["shopper_id"])


def downgrade() -> None:
    op.drop_index("ix_ecommerce_orders_shopper_id", table_name="ecommerce_orders")
    op.drop_column("ecommerce_orders", "shopper_id")
    op.drop_column("ecommerce_reservations", "variant_id")
    op.drop_column("ecommerce_order_items", "variant_id")
    with op.batch_alter_table("ecommerce_cart_items") as batch:
        batch.drop_constraint("uq_ecommerce_cart_items_line", type_="unique")
        batch.create_unique_constraint(
            "ecommerce_cart_items_cart_id_product_id_key",
            ["cart_id", "product_id"],
        )
        batch.drop_column("variant_id")
    op.drop_table("ecommerce_shoppers")
