"""ADR-490 phase 20 — company-scoped product/variant barcode uniqueness.

Revision ID: 20260814_0102
Revises: 20260814_0101
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260814_0102"
down_revision = "20260814_0101"
branch_labels = None
depends_on = None


def _create_barcode_unique(table: str) -> None:
    # Partial unique so multiple NULL barcodes remain allowed.
    op.execute(
        sa.text(
            f"CREATE UNIQUE INDEX IF NOT EXISTS uq_{table}_tenant_company_barcode "
            f"ON {table} (tenant_id, company_id, barcode) "
            f"WHERE barcode IS NOT NULL"
        )
    )


def _drop_barcode_unique(table: str) -> None:
    op.execute(sa.text(f"DROP INDEX IF EXISTS uq_{table}_tenant_company_barcode"))


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table in ("products", "product_variants"):
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "company_id" not in cols or "barcode" not in cols:
            continue
        op.execute(
            sa.text(
                f"UPDATE {table} SET company_id = ("
                f"SELECT c.id FROM companies c WHERE c.tenant_id = {table}.tenant_id "
                f"AND c.is_default = true LIMIT 1) "
                f"WHERE company_id IS NULL"
            )
        )
        _create_barcode_unique(table)


def downgrade() -> None:
    for table in ("products", "product_variants"):
        _drop_barcode_unique(table)
