"""Coupons, other income, product created_by (tables / columns if missing).

Revision ID: 20260928_0123
Revises: 20260928_0122

Former 20260928_0106_coupons_income_product_created.py collided with printer
0106. Unique revision after hotel 0121 + minimum_stock 0122.
Does not add sales_invoices.coupon_id (that is 0124).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260928_0123"
down_revision = "20260928_0122"
branch_labels = None
depends_on = None


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    insp = inspect(bind)
    if table not in insp.get_table_names():
        return set()
    return {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    product_cols = _column_names("products")
    if "created_by" not in product_cols:
        op.add_column("products", sa.Column("created_by", sa.String(length=36), nullable=True))

    tables = _table_names()
    if "sales_coupons" not in tables:
        op.create_table(
            "sales_coupons",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("discount_type", sa.String(length=16), nullable=False, server_default="percent"),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("min_spend", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("starts_at", sa.DateTime(), nullable=True),
            sa.Column("ends_at", sa.DateTime(), nullable=True),
            sa.Column("max_redemptions", sa.Integer(), nullable=True),
            sa.Column("per_customer_limit", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("eligible_product_ids", sa.JSON(), nullable=True),
            sa.Column("eligible_category_ids", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_sales_coupons_tenant_code"),
        )
        op.create_index("ix_sales_coupons_tenant_id", "sales_coupons", ["tenant_id"])
    elif "ix_sales_coupons_tenant_id" not in _index_names("sales_coupons"):
        op.create_index("ix_sales_coupons_tenant_id", "sales_coupons", ["tenant_id"])

    tables = _table_names()
    if "sales_coupon_redemptions" not in tables:
        op.create_table(
            "sales_coupon_redemptions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "coupon_id",
                sa.String(length=36),
                sa.ForeignKey("sales_coupons.id"),
                nullable=False,
            ),
            sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("parties.id"), nullable=True),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("source_id", sa.String(length=36), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_sales_coupon_redemptions_tenant_id", "sales_coupon_redemptions", ["tenant_id"])
        op.create_index("ix_sales_coupon_redemptions_coupon_id", "sales_coupon_redemptions", ["coupon_id"])

    tables = _table_names()
    if "other_incomes" not in tables:
        op.create_table(
            "other_incomes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False),
            sa.Column("income_date", sa.DateTime(), nullable=False),
            sa.Column("payment_method", sa.String(length=40), nullable=False, server_default="cash"),
            sa.Column("liquid_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
            sa.Column("payer", sa.String(length=150), nullable=True),
            sa.Column("reference", sa.String(length=100), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="posted"),
            sa.Column("journal_entry_id", sa.String(length=36), sa.ForeignKey("journal_entries.id"), nullable=True),
            sa.Column("created_by", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_other_incomes_tenant_id", "other_incomes", ["tenant_id"])


def downgrade() -> None:
    return
