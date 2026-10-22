"""Tenant ecommerce storefront, domains, orders, gateways, connectors.

Revision ID: 20261021_0139
Revises: 20261011_0138
Create Date: 2026-10-21

Additive only. Does not stamp or upgrade a live database.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261021_0139"
down_revision = "20261011_0138"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ecommerce_storefronts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tagline", sa.String(200), nullable=True),
        sa.Column("announcement", sa.String(500), nullable=True),
        sa.Column("support_email", sa.String(255), nullable=True),
        sa.Column("support_phone", sa.String(40), nullable=True),
        sa.Column("fulfillment_warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("fulfillment_store_id", sa.String(36), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("allow_delivery", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allow_pickup", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pickup_address", sa.Text(), nullable=True),
        sa.Column("delivery_notes", sa.Text(), nullable=True),
        sa.Column("policy_shipping", sa.Text(), nullable=True),
        sa.Column("policy_returns", sa.Text(), nullable=True),
        sa.Column("policy_privacy", sa.Text(), nullable=True),
        sa.Column("reservation_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("preview_token", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id"),
        sa.UniqueConstraint("preview_token"),
    )
    op.create_table(
        "ecommerce_domains",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("https_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("redirect_to_id", sa.String(36), sa.ForeignKey("ecommerce_domains.id"), nullable=True),
        sa.Column("verification_token", sa.String(80), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("hostname", name="uq_ecommerce_domains_hostname"),
    )
    op.create_index(
        "ix_ecommerce_domains_tenant_status",
        "ecommerce_domains",
        ["tenant_id", "status"],
    )
    op.create_table(
        "ecommerce_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False, index=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("online_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("stock_buffer", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("fulfillment_warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("external_id", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "product_id"),
    )
    op.create_index("ix_ecommerce_listings_external_id", "ecommerce_listings", ["external_id"])
    op.create_table(
        "ecommerce_carts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("token", sa.String(80), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("token"),
    )
    op.create_table(
        "ecommerce_cart_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("cart_id", sa.String(36), sa.ForeignKey("ecommerce_carts.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.UniqueConstraint("cart_id", "product_id"),
    )
    op.create_table(
        "ecommerce_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_number", sa.String(40), nullable=False),
        sa.Column("tracking_token", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="awaiting_payment"),
        sa.Column("fulfillment", sa.String(20), nullable=False, server_default="delivery"),
        sa.Column("guest_name", sa.String(180), nullable=False),
        sa.Column("guest_email", sa.String(255), nullable=True),
        sa.Column("guest_phone", sa.String(40), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="GHS"),
        sa.Column("party_id", sa.String(36), sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("sales_invoice_id", sa.String(36), sa.ForeignKey("sales_invoices.id"), nullable=True),
        sa.Column("payment_reference", sa.String(80), nullable=True),
        sa.Column("payment_provider", sa.String(40), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("reserved_until", sa.DateTime(), nullable=True),
        sa.Column("external_id", sa.String(80), nullable=True),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=True),
        sa.Column("store_id", sa.String(36), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "order_number"),
        sa.UniqueConstraint("tenant_id", "tracking_token"),
        sa.UniqueConstraint("tenant_id", "external_id"),
    )
    op.create_index("ix_ecommerce_orders_tenant_status", "ecommerce_orders", ["tenant_id", "status"])
    op.create_table(
        "ecommerce_order_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("ecommerce_orders.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
    )
    op.create_table(
        "ecommerce_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("ecommerce_orders.id"), nullable=False, index=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_ecommerce_reservations_active",
        "ecommerce_reservations",
        ["tenant_id", "status", "warehouse_id"],
    )
    op.create_table(
        "ecommerce_gateways",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False, server_default="mock"),
        sa.Column("mode", sa.String(10), nullable=False, server_default="test"),
        sa.Column("secret_enc", sa.Text(), nullable=True),
        sa.Column("webhook_secret_enc", sa.Text(), nullable=True),
        sa.Column("public_key_hint", sa.String(40), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_table(
        "ecommerce_payment_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("ecommerce_orders.id"), nullable=True),
        sa.Column("payload_digest", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "provider", "event_id"),
    )
    op.create_table(
        "ecommerce_connectors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("platform", sa.String(40), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("store_url", sa.String(255), nullable=True),
        sa.Column("credentials_enc", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "platform"),
    )
    op.create_table(
        "ecommerce_sync_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("connector_id", sa.String(36), sa.ForeignKey("ecommerce_connectors.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stats", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ecommerce_sync_jobs_tenant", "ecommerce_sync_jobs", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ecommerce_sync_jobs_tenant", table_name="ecommerce_sync_jobs")
    op.drop_table("ecommerce_sync_jobs")
    op.drop_table("ecommerce_connectors")
    op.drop_table("ecommerce_payment_events")
    op.drop_table("ecommerce_gateways")
    op.drop_index("ix_ecommerce_reservations_active", table_name="ecommerce_reservations")
    op.drop_table("ecommerce_reservations")
    op.drop_table("ecommerce_order_items")
    op.drop_index("ix_ecommerce_orders_tenant_status", table_name="ecommerce_orders")
    op.drop_table("ecommerce_orders")
    op.drop_table("ecommerce_cart_items")
    op.drop_table("ecommerce_carts")
    op.drop_index("ix_ecommerce_listings_external_id", table_name="ecommerce_listings")
    op.drop_table("ecommerce_listings")
    op.drop_index("ix_ecommerce_domains_tenant_status", table_name="ecommerce_domains")
    op.drop_table("ecommerce_domains")
    op.drop_table("ecommerce_storefronts")
