"""Till lock with cashier passcodes, and the restaurant digital menu.

Revision ID: 20261105_0153
Revises: 20261031_0152
Create Date: 2026-11-05

Adds cashier passcodes, per-till operator sessions and wrong-passcode throttles,
records who took the money on a restaurant order, and gives each restaurant its
own menu tables. Skipped where a table or column already exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_0153"
down_revision = "20261031_0152"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    return column in {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_table("pos_cashier_passcodes"):
        op.create_table(
            "pos_cashier_passcodes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("lookup_hash", sa.String(length=64), nullable=False),
            sa.Column("passcode_hash", sa.String(length=255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "user_id", name="uq_pos_cashier_passcode_user"),
        )
        op.create_index("ix_pos_cashier_passcodes_tenant_id", "pos_cashier_passcodes", ["tenant_id"])
        op.create_index("ix_pos_cashier_passcodes_user_id", "pos_cashier_passcodes", ["user_id"])
        op.create_index(
            "uq_pos_cashier_passcode_active_lookup",
            "pos_cashier_passcodes",
            ["tenant_id", "lookup_hash"],
            unique=True,
            postgresql_where=sa.text("is_active"),
            sqlite_where=sa.text("is_active = 1"),
        )

    if not _has_table("pos_operator_sessions"):
        op.create_table(
            "pos_operator_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("surface", sa.String(length=20), nullable=False),
            sa.Column("device_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("login_user_id", sa.String(length=36), nullable=True),
            sa.Column("unlock_method", sa.String(length=20), nullable=False),
            sa.Column("previous_session_id", sa.String(length=36), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("last_activity_at", sa.DateTime(), nullable=False),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("end_reason", sa.String(length=30), nullable=True),
        )
        op.create_index("ix_pos_operator_sessions_tenant_id", "pos_operator_sessions", ["tenant_id"])
        op.create_index("ix_pos_operator_sessions_device_id", "pos_operator_sessions", ["device_id"])
        op.create_index("ix_pos_operator_sessions_user_id", "pos_operator_sessions", ["user_id"])
        op.create_index(
            "uq_pos_operator_session_live",
            "pos_operator_sessions",
            ["tenant_id", "device_id", "surface"],
            unique=True,
            postgresql_where=sa.text("ended_at IS NULL"),
            sqlite_where=sa.text("ended_at IS NULL"),
        )

    if not _has_table("pos_unlock_throttles"):
        op.create_table(
            "pos_unlock_throttles",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("scope_key", sa.String(length=120), nullable=False),
            sa.Column("failed_count", sa.Integer(), nullable=False),
            sa.Column("window_started_at", sa.DateTime(), nullable=False),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("tenant_id", "scope_key", name="uq_pos_unlock_throttle_scope"),
        )
        op.create_index("ix_pos_unlock_throttles_tenant_id", "pos_unlock_throttles", ["tenant_id"])

    if not _has_column("restaurant_orders", "completed_by"):
        op.add_column("restaurant_orders", sa.Column("completed_by", sa.String(length=36), nullable=True))
        op.create_index("ix_restaurant_orders_completed_by", "restaurant_orders", ["completed_by"])
    if not _has_column("restaurant_orders", "completed_device_id"):
        op.add_column("restaurant_orders", sa.Column("completed_device_id", sa.String(length=64), nullable=True))

    if not _has_table("restaurant_menu_settings"):
        op.create_table(
            "restaurant_menu_settings",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("public_token", sa.String(length=48), nullable=False),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("tagline", sa.String(length=160), nullable=True),
            sa.Column("accent_color", sa.String(length=7), nullable=False, server_default="#4AB012"),
            sa.Column("board_style", sa.String(length=20), nullable=False, server_default="forest"),
            sa.Column("board_rotate_seconds", sa.Integer(), nullable=False, server_default="12"),
            sa.Column("show_unavailable", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", name="uq_restaurant_menu_settings_tenant"),
            sa.UniqueConstraint("public_token", name="uq_restaurant_menu_public_token"),
        )
        op.create_index("ix_restaurant_menu_settings_tenant_id", "restaurant_menu_settings", ["tenant_id"])

    if not _has_table("restaurant_menu_categories"):
        op.create_table(
            "restaurant_menu_categories",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "name", name="uq_restaurant_menu_category_name"),
        )
        op.create_index("ix_restaurant_menu_categories_tenant_id", "restaurant_menu_categories", ["tenant_id"])

    if not _has_table("restaurant_menu_items"):
        op.create_table(
            "restaurant_menu_items",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "category_id", sa.String(length=36), sa.ForeignKey("restaurant_menu_categories.id"), nullable=False
            ),
            sa.Column("product_id", sa.String(length=36), sa.ForeignKey("products.id"), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("promo_label", sa.String(length=60), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "product_id", name="uq_restaurant_menu_item_product"),
        )
        op.create_index("ix_restaurant_menu_items_tenant_id", "restaurant_menu_items", ["tenant_id"])
        op.create_index("ix_restaurant_menu_items_category_id", "restaurant_menu_items", ["category_id"])
        op.create_index("ix_restaurant_menu_items_product_id", "restaurant_menu_items", ["product_id"])


def downgrade() -> None:
    for table in (
        "restaurant_menu_items",
        "restaurant_menu_categories",
        "restaurant_menu_settings",
        "pos_unlock_throttles",
        "pos_operator_sessions",
        "pos_cashier_passcodes",
    ):
        if _has_table(table):
            op.drop_table(table)
    if _has_column("restaurant_orders", "completed_device_id"):
        op.drop_column("restaurant_orders", "completed_device_id")
    if _has_column("restaurant_orders", "completed_by"):
        op.drop_index("ix_restaurant_orders_completed_by", table_name="restaurant_orders")
        op.drop_column("restaurant_orders", "completed_by")
