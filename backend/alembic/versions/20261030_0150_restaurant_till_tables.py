"""Restaurant till tables (front-of-house split).

Revision ID: 20261030_0150
Revises: 20261026_0149
Create Date: 2026-10-30

The restaurant till gets its own shifts, cash moves, receipts, receipt lines,
payments, returns and return lines, so a restaurant company never writes the
retail POS tables. This revision only creates the tables; existing restaurant
till rows are moved when the restaurant till switches over
(docs/RESTAURANT_FRONT_OF_HOUSE_SPLIT.md). Each table is skipped when it exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261030_0150"
down_revision = "20261026_0149"
branch_labels = None
depends_on = None

# Parents before children.
TABLES = (
    "restaurant_till_shifts",
    "restaurant_till_cash_moves",
    "restaurant_till_receipts",
    "restaurant_till_receipt_lines",
    "restaurant_till_payments",
    "restaurant_till_returns",
    "restaurant_till_return_lines",
)


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, 'restaurant_till_shifts'):
        op.create_table(
            'restaurant_till_shifts',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('store_id', sa.String(length=36), sa.ForeignKey('stores.id'), nullable=True),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('shift_number', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('opening_cash', sa.Numeric(14, 2), nullable=False),
            sa.Column('expected_cash', sa.Numeric(14, 2), nullable=False),
            sa.Column('actual_cash', sa.Numeric(14, 2), nullable=True),
            sa.Column('cash_sales', sa.Numeric(14, 2), nullable=False),
            sa.Column('cash_in', sa.Numeric(14, 2), nullable=False),
            sa.Column('cash_out', sa.Numeric(14, 2), nullable=False),
            sa.Column('card_sales', sa.Numeric(14, 2), nullable=False),
            sa.Column('other_sales', sa.Numeric(14, 2), nullable=False),
            sa.Column('total_sales', sa.Numeric(14, 2), nullable=False),
            sa.Column('sale_count', sa.Integer(), nullable=False),
            sa.Column('variance', sa.Numeric(14, 2), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('opened_at', sa.DateTime(), nullable=False),
            sa.Column('closed_at', sa.DateTime(), nullable=True),
            sa.UniqueConstraint('tenant_id', 'shift_number', name='uq_restaurant_till_shift_number'),
        )
        op.create_index('ix_restaurant_till_shifts_shift_number', 'restaurant_till_shifts', ['shift_number'])
        op.create_index('ix_restaurant_till_shifts_status', 'restaurant_till_shifts', ['status'])
        op.create_index('ix_restaurant_till_shifts_store_id', 'restaurant_till_shifts', ['store_id'])
        op.create_index('ix_restaurant_till_shifts_tenant_id', 'restaurant_till_shifts', ['tenant_id'])
        op.create_index('ix_restaurant_till_shifts_user_id', 'restaurant_till_shifts', ['user_id'])
        op.create_index('uq_restaurant_till_shifts_one_open_per_user', 'restaurant_till_shifts', ['tenant_id', 'user_id'], unique=True, postgresql_where=sa.text("status = 'open'"), sqlite_where=sa.text("status = 'open'"))
    if not _has_table(bind, 'restaurant_till_cash_moves'):
        op.create_table(
            'restaurant_till_cash_moves',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('shift_id', sa.String(length=36), sa.ForeignKey('restaurant_till_shifts.id'), nullable=False),
            sa.Column('store_id', sa.String(length=36), sa.ForeignKey('stores.id'), nullable=True),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('movement_type', sa.String(length=20), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('reason', sa.String(length=200), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_restaurant_till_cash_moves_movement_type', 'restaurant_till_cash_moves', ['movement_type'])
        op.create_index('ix_restaurant_till_cash_moves_shift_id', 'restaurant_till_cash_moves', ['shift_id'])
        op.create_index('ix_restaurant_till_cash_moves_store_id', 'restaurant_till_cash_moves', ['store_id'])
        op.create_index('ix_restaurant_till_cash_moves_tenant_id', 'restaurant_till_cash_moves', ['tenant_id'])
        op.create_index('ix_restaurant_till_cash_moves_user_id', 'restaurant_till_cash_moves', ['user_id'])
    if not _has_table(bind, 'restaurant_till_receipts'):
        op.create_table(
            'restaurant_till_receipts',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('receipt_number', sa.String(length=80), nullable=False),
            sa.Column('shift_id', sa.String(length=36), sa.ForeignKey('restaurant_till_shifts.id'), nullable=True),
            sa.Column('store_id', sa.String(length=36), sa.ForeignKey('stores.id'), nullable=True),
            sa.Column('customer_id', sa.String(length=36), sa.ForeignKey('parties.id'), nullable=True),
            sa.Column('customer_name', sa.String(length=180), nullable=True),
            sa.Column('client_request_id', sa.String(length=64), nullable=True),
            sa.Column('payment_method', sa.String(length=40), nullable=False),
            sa.Column('subtotal', sa.Numeric(14, 2), nullable=False),
            sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('tax', sa.Numeric(14, 2), nullable=False),
            sa.Column('total', sa.Numeric(14, 2), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('created_by', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('tenant_id', 'client_request_id', name='uq_restaurant_till_receipt_request'),
            sa.UniqueConstraint('tenant_id', 'receipt_number', name='uq_restaurant_till_receipt_number'),
        )
        op.create_index('ix_restaurant_till_receipts_client_request_id', 'restaurant_till_receipts', ['client_request_id'])
        op.create_index('ix_restaurant_till_receipts_created_at', 'restaurant_till_receipts', ['created_at'])
        op.create_index('ix_restaurant_till_receipts_customer_id', 'restaurant_till_receipts', ['customer_id'])
        op.create_index('ix_restaurant_till_receipts_receipt_number', 'restaurant_till_receipts', ['receipt_number'])
        op.create_index('ix_restaurant_till_receipts_shift_id', 'restaurant_till_receipts', ['shift_id'])
        op.create_index('ix_restaurant_till_receipts_status', 'restaurant_till_receipts', ['status'])
        op.create_index('ix_restaurant_till_receipts_store_id', 'restaurant_till_receipts', ['store_id'])
        op.create_index('ix_restaurant_till_receipts_tenant_id', 'restaurant_till_receipts', ['tenant_id'])
    if not _has_table(bind, 'restaurant_till_receipt_lines'):
        op.create_table(
            'restaurant_till_receipt_lines',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('receipt_id', sa.String(length=36), sa.ForeignKey('restaurant_till_receipts.id'), nullable=False),
            sa.Column('product_id', sa.String(length=36), sa.ForeignKey('products.id'), nullable=False),
            sa.Column('name', sa.String(length=200), nullable=False),
            sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
            sa.Column('unit_price', sa.Numeric(14, 2), nullable=False),
            sa.Column('discount', sa.Numeric(14, 2), nullable=False),
            sa.Column('tax_rate', sa.Numeric(7, 4), nullable=False),
            sa.Column('line_total', sa.Numeric(14, 2), nullable=False),
        )
        op.create_index('ix_restaurant_till_receipt_lines_product_id', 'restaurant_till_receipt_lines', ['product_id'])
        op.create_index('ix_restaurant_till_receipt_lines_receipt_id', 'restaurant_till_receipt_lines', ['receipt_id'])
        op.create_index('ix_restaurant_till_receipt_lines_tenant_id', 'restaurant_till_receipt_lines', ['tenant_id'])
    if not _has_table(bind, 'restaurant_till_payments'):
        op.create_table(
            'restaurant_till_payments',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('receipt_id', sa.String(length=36), sa.ForeignKey('restaurant_till_receipts.id'), nullable=False),
            sa.Column('payment_method', sa.String(length=40), nullable=False),
            sa.Column('amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('reference', sa.String(length=100), nullable=True),
            sa.Column('liquid_account_id', sa.String(length=36), sa.ForeignKey('accounts.id'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
        )
        op.create_index('ix_restaurant_till_payments_receipt_id', 'restaurant_till_payments', ['receipt_id'])
        op.create_index('ix_restaurant_till_payments_tenant_id', 'restaurant_till_payments', ['tenant_id'])
    if not _has_table(bind, 'restaurant_till_returns'):
        op.create_table(
            'restaurant_till_returns',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('return_number', sa.String(length=50), nullable=False),
            sa.Column('receipt_id', sa.String(length=36), sa.ForeignKey('restaurant_till_receipts.id'), nullable=False),
            sa.Column('shift_id', sa.String(length=36), sa.ForeignKey('restaurant_till_shifts.id'), nullable=True),
            sa.Column('store_id', sa.String(length=36), sa.ForeignKey('stores.id'), nullable=True),
            sa.Column('customer_id', sa.String(length=36), sa.ForeignKey('parties.id'), nullable=True),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('reason', sa.String(length=80), nullable=False),
            sa.Column('subtotal', sa.Numeric(14, 2), nullable=False),
            sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('total_amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('refund_payment_method', sa.String(length=30), nullable=True),
            sa.Column('refunded_amount', sa.Numeric(14, 2), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_by', sa.String(length=36), nullable=True),
            sa.Column('posted_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.UniqueConstraint('tenant_id', 'return_number', name='uq_restaurant_till_return_number'),
        )
        op.create_index('ix_restaurant_till_returns_customer_id', 'restaurant_till_returns', ['customer_id'])
        op.create_index('ix_restaurant_till_returns_posted_at', 'restaurant_till_returns', ['posted_at'])
        op.create_index('ix_restaurant_till_returns_receipt_id', 'restaurant_till_returns', ['receipt_id'])
        op.create_index('ix_restaurant_till_returns_return_number', 'restaurant_till_returns', ['return_number'])
        op.create_index('ix_restaurant_till_returns_shift_id', 'restaurant_till_returns', ['shift_id'])
        op.create_index('ix_restaurant_till_returns_status', 'restaurant_till_returns', ['status'])
        op.create_index('ix_restaurant_till_returns_store_id', 'restaurant_till_returns', ['store_id'])
        op.create_index('ix_restaurant_till_returns_tenant_id', 'restaurant_till_returns', ['tenant_id'])
    if not _has_table(bind, 'restaurant_till_return_lines'):
        op.create_table(
            'restaurant_till_return_lines',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('tenant_id', sa.String(length=36), sa.ForeignKey('tenants.id'), nullable=False),
            sa.Column('return_id', sa.String(length=36), sa.ForeignKey('restaurant_till_returns.id'), nullable=False),
            sa.Column('receipt_line_id', sa.String(length=36), sa.ForeignKey('restaurant_till_receipt_lines.id'), nullable=True),
            sa.Column('product_id', sa.String(length=36), sa.ForeignKey('products.id'), nullable=False),
            sa.Column('quantity', sa.Numeric(14, 3), nullable=False),
            sa.Column('unit_price', sa.Numeric(14, 2), nullable=False),
            sa.Column('tax_rate', sa.Numeric(7, 4), nullable=False),
            sa.Column('line_total', sa.Numeric(14, 2), nullable=False),
            sa.Column('restock', sa.Boolean(), nullable=False),
        )
        op.create_index('ix_restaurant_till_return_lines_product_id', 'restaurant_till_return_lines', ['product_id'])
        op.create_index('ix_restaurant_till_return_lines_receipt_line_id', 'restaurant_till_return_lines', ['receipt_line_id'])
        op.create_index('ix_restaurant_till_return_lines_return_id', 'restaurant_till_return_lines', ['return_id'])
        op.create_index('ix_restaurant_till_return_lines_tenant_id', 'restaurant_till_return_lines', ['tenant_id'])



def downgrade() -> None:
    bind = op.get_bind()
    for name in reversed(TABLES):
        if _has_table(bind, name):
            op.drop_table(name)
