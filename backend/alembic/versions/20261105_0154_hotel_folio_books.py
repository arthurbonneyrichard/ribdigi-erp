"""Hotel folios reach the ledger, and the hotel tax setting takes effect.

Revision ID: 20261105_0154
Revises: 20261105_0153
Create Date: 2026-11-05

Links folio charges and payments to their journals, adds refunds of a folio
payment, keeps the cash taken on a front-desk float so it can be counted, and
records whether room rates already include tax. Rates stay as quoted
by default. Skipped where a column already exists.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261105_0154"
down_revision = "20261105_0153"
branch_labels = None
depends_on = None

COLUMNS = (
    ("hotel_folio_charges", sa.Column("journal_entry_id", sa.String(36), nullable=True)),
    ("hotel_folio_payments", sa.Column("journal_entry_id", sa.String(36), nullable=True)),
    ("hotel_folio_payments", sa.Column("refund_of_id", sa.String(36), nullable=True)),
    ("hotel_cashier_shifts", sa.Column("cash_total", sa.Numeric(14, 2), nullable=True)),
    ("hotel_settings", sa.Column("room_rates_include_tax", sa.Boolean(), nullable=False, server_default=sa.true())),
)


def _has_column(table: str, column: str) -> bool:
    return column in {col["name"] for col in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for table, column in COLUMNS:
        if not _has_column(table, column.name):
            op.add_column(table, column.copy())


def downgrade() -> None:
    for table, column in reversed(COLUMNS):
        if _has_column(table, column.name):
            op.drop_column(table, column.name)
