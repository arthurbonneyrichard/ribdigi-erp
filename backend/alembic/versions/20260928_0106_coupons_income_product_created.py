"""Coupons, other income, product created_by, invoice coupon_id.

Revision ID: 20260928_0106
Revises: 20260816_0105
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0106"
down_revision = "20260816_0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("created_by", sa.String(length=36), nullable=True))
    op.add_column("sales_invoices", sa.Column("coupon_id", sa.String(length=36), nullable=True))
    op.create_index("ix_sales_invoices_coupon_id", "sales_invoices", ["coupon_id"])

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
    op.drop_table("other_incomes")
    op.drop_table("sales_coupon_redemptions")
    op.drop_table("sales_coupons")
    op.drop_index("ix_sales_invoices_coupon_id", table_name="sales_invoices")
    op.drop_column("sales_invoices", "coupon_id")
    op.drop_column("products", "created_by")
