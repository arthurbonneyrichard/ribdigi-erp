"""Restaurant floor tables and platform billing gateway credentials.

Revision ID: 20261008_0135
Revises: 20261008_0117
Create Date: 2026-10-08

Creates tables only when missing so a database that already has them
from model create_all is left unchanged. Existing tenant rows are not
updated.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261008_0135"
down_revision = "20261008_0117"
branch_labels = None
depends_on = None


def _names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    names = _names()
    if "platform_billing_gateways" not in names:
        op.create_table(
            "platform_billing_gateways",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="mock"),
            sa.Column("mode", sa.String(length=16), nullable=False, server_default="sandbox"),
            sa.Column("api_base_url", sa.String(length=200), nullable=True),
            sa.Column("secret_enc", sa.Text(), nullable=True),
            sa.Column("webhook_secret_enc", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("last_test_ok", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("last_test_at", sa.DateTime(), nullable=True),
            sa.Column("last_test_message", sa.String(length=80), nullable=True),
            sa.Column("last_webhook_at", sa.DateTime(), nullable=True),
            sa.Column("last_webhook_outcome", sa.String(length=40), nullable=True),
            sa.Column("updated_by", sa.String(length=36), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if "restaurant_tables" not in names:
        op.create_table(
            "restaurant_tables",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("store_id", sa.String(length=36), nullable=True),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("seats", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="available"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "code", name="uq_restaurant_table_code"),
        )
        op.create_index("ix_restaurant_tables_tenant_id", "restaurant_tables", ["tenant_id"])
        op.create_index("ix_restaurant_tables_store_id", "restaurant_tables", ["store_id"])
    if "restaurant_modifier_groups" not in names:
        op.create_table(
            "restaurant_modifier_groups",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_restaurant_modifier_groups_tenant_id", "restaurant_modifier_groups", ["tenant_id"])
    if "restaurant_modifiers" not in names:
        op.create_table(
            "restaurant_modifiers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("group_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("price", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["group_id"], ["restaurant_modifier_groups.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_restaurant_modifiers_tenant_id", "restaurant_modifiers", ["tenant_id"])
        op.create_index("ix_restaurant_modifiers_group_id", "restaurant_modifiers", ["group_id"])
    if "restaurant_recipes" not in names:
        op.create_table(
            "restaurant_recipes",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("product_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "product_id", name="uq_restaurant_recipe_product"),
        )
        op.create_index("ix_restaurant_recipes_tenant_id", "restaurant_recipes", ["tenant_id"])
        op.create_index("ix_restaurant_recipes_product_id", "restaurant_recipes", ["product_id"])
    if "restaurant_recipe_lines" not in names:
        op.create_table(
            "restaurant_recipe_lines",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("recipe_id", sa.String(length=36), nullable=False),
            sa.Column("ingredient_id", sa.String(length=36), nullable=False),
            sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["recipe_id"], ["restaurant_recipes.id"]),
            sa.ForeignKeyConstraint(["ingredient_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_restaurant_recipe_lines_tenant_id", "restaurant_recipe_lines", ["tenant_id"])
        op.create_index("ix_restaurant_recipe_lines_recipe_id", "restaurant_recipe_lines", ["recipe_id"])
    if "restaurant_orders" not in names:
        op.create_table(
            "restaurant_orders",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("store_id", sa.String(length=36), nullable=True),
            sa.Column("order_number", sa.String(length=40), nullable=False),
            sa.Column("service_mode", sa.String(length=20), nullable=False),
            sa.Column("table_id", sa.String(length=36), nullable=True),
            sa.Column("customer_name", sa.String(length=180), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("payment_method", sa.String(length=32), nullable=False, server_default="cash"),
            sa.Column("subtotal", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("total_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("journal_entry_id", sa.String(length=36), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
            sa.ForeignKeyConstraint(["table_id"], ["restaurant_tables.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "order_number", name="uq_restaurant_order_number"),
        )
        op.create_index("ix_restaurant_orders_tenant_id", "restaurant_orders", ["tenant_id"])
        op.create_index("ix_restaurant_orders_store_id", "restaurant_orders", ["store_id"])
    if "restaurant_order_lines" not in names:
        op.create_table(
            "restaurant_order_lines",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("order_id", sa.String(length=36), nullable=False),
            sa.Column("product_id", sa.String(length=36), nullable=False),
            sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
            sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("line_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("station", sa.String(length=20), nullable=False, server_default="kitchen"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["order_id"], ["restaurant_orders.id"]),
            sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_restaurant_order_lines_tenant_id", "restaurant_order_lines", ["tenant_id"])
        op.create_index("ix_restaurant_order_lines_order_id", "restaurant_order_lines", ["order_id"])
    if "restaurant_order_modifiers" not in names:
        op.create_table(
            "restaurant_order_modifiers",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("line_id", sa.String(length=36), nullable=False),
            sa.Column("modifier_id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("price", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["line_id"], ["restaurant_order_lines.id"]),
            sa.ForeignKeyConstraint(["modifier_id"], ["restaurant_modifiers.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_restaurant_order_modifiers_line_id", "restaurant_order_modifiers", ["line_id"])
    if "restaurant_kitchen_tickets" not in names:
        op.create_table(
            "restaurant_kitchen_tickets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("tenant_id", sa.String(length=36), nullable=False),
            sa.Column("order_id", sa.String(length=36), nullable=False),
            sa.Column("station", sa.String(length=20), nullable=False, server_default="kitchen"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["order_id"], ["restaurant_orders.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_restaurant_kitchen_tickets_tenant_id", "restaurant_kitchen_tickets", ["tenant_id"])
        op.create_index("ix_restaurant_kitchen_tickets_order_id", "restaurant_kitchen_tickets", ["order_id"])


def downgrade() -> None:
    names = _names()
    for table in (
        "restaurant_kitchen_tickets",
        "restaurant_order_modifiers",
        "restaurant_order_lines",
        "restaurant_orders",
        "restaurant_recipe_lines",
        "restaurant_recipes",
        "restaurant_modifiers",
        "restaurant_modifier_groups",
        "restaurant_tables",
        "platform_billing_gateways",
    ):
        if table in names:
            op.drop_table(table)
