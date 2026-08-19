"""ADR-490 phase 16 — company document numbering + doc-number uniques.

Revision ID: 20260814_0099
Revises: 20260814_0098
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260814_0099"
down_revision = "20260814_0098"
branch_labels = None
depends_on = None

DOC_UNIQUE_CHANGES = [
    ("sales_invoices", ["tenant_id", "invoice_number"], ["tenant_id", "company_id", "invoice_number"]),
    ("purchase_invoices", ["tenant_id", "invoice_number"], ["tenant_id", "company_id", "invoice_number"]),
    ("purchase_orders", ["tenant_id", "po_number"], ["tenant_id", "company_id", "po_number"]),
    ("goods_receipts", ["tenant_id", "grn_number"], ["tenant_id", "company_id", "grn_number"]),
    ("sales_quotations", ["tenant_id", "quotation_number"], ["tenant_id", "company_id", "quotation_number"]),
    ("sales_orders", ["tenant_id", "order_number"], ["tenant_id", "company_id", "order_number"]),
    ("sales_returns", ["tenant_id", "return_number"], ["tenant_id", "company_id", "return_number"]),
    ("purchase_returns", ["tenant_id", "return_number"], ["tenant_id", "company_id", "return_number"]),
]


def _drop_matching_unique(insp, table: str, cols: list[str]) -> None:
    want = set(cols)
    for uq in insp.get_unique_constraints(table) or []:
        if set(uq.get("column_names") or []) == want:
            op.drop_constraint(uq["name"], table_name=table, type_="unique")
            return
    for ix in insp.get_indexes(table) or []:
        if ix.get("unique") and set(ix.get("column_names") or []) == want:
            op.drop_index(ix["name"], table_name=table)
            return


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "companies" in tables:
        cols = {c["name"] for c in insp.get_columns("companies")}
        if "document_numbering" not in cols:
            op.add_column(
                "companies",
                sa.Column("document_numbering", sa.JSON(), nullable=True),
            )
        # Backfill company series from tenant legacy JSON.
        op.execute(
            sa.text(
                "UPDATE companies SET document_numbering = ("
                "SELECT t.document_numbering FROM tenants t "
                "WHERE t.id = companies.tenant_id"
                ") WHERE document_numbering IS NULL"
            )
        )

    for table, old_cols, new_cols in DOC_UNIQUE_CHANGES:
        if table not in tables:
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "company_id" not in cols:
            continue
        op.execute(
            sa.text(
                f"UPDATE {table} SET company_id = ("
                f"SELECT c.id FROM companies c WHERE c.tenant_id = {table}.tenant_id "
                f"AND c.is_default = true LIMIT 1) "
                f"WHERE company_id IS NULL"
            )
        )
        _drop_matching_unique(insp, table, old_cols)
        op.create_unique_constraint(
            f"uq_{table}_tenant_company_{new_cols[-1]}",
            table,
            new_cols,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table, old_cols, new_cols in DOC_UNIQUE_CHANGES:
        if table not in tables:
            continue
        name = f"uq_{table}_tenant_company_{new_cols[-1]}"
        try:
            op.drop_constraint(name, table_name=table, type_="unique")
        except Exception:
            pass
        op.create_unique_constraint(f"uq_{table}_{'_'.join(old_cols)}", table, old_cols)
    if "companies" in tables:
        cols = {c["name"] for c in insp.get_columns("companies")}
        if "document_numbering" in cols:
            op.drop_column("companies", "document_numbering")
