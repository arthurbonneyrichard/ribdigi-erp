"""ADR-490 phase 18 — company-scoped ops number uniques.

Revision ID: 20260814_0101
Revises: 20260814_0100
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260814_0101"
down_revision = "20260814_0100"
branch_labels = None
depends_on = None

UNIQUE_CHANGES = [
    ("customer_payments", ["tenant_id", "payment_number"], ["tenant_id", "company_id", "payment_number"]),
    ("supplier_payments", ["tenant_id", "payment_number"], ["tenant_id", "company_id", "payment_number"]),
    ("pos_sessions", ["tenant_id", "session_number"], ["tenant_id", "company_id", "session_number"]),
    ("journal_entries", ["tenant_id", "entry_number"], ["tenant_id", "company_id", "entry_number"]),
    ("stock_transfers", ["tenant_id", "transfer_number"], ["tenant_id", "company_id", "transfer_number"]),
    ("stock_counts", ["tenant_id", "count_number"], ["tenant_id", "company_id", "count_number"]),
    ("purchase_requests", ["tenant_id", "request_number"], ["tenant_id", "company_id", "request_number"]),
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
    for table, old_cols, new_cols in UNIQUE_CHANGES:
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
    for table, old_cols, new_cols in UNIQUE_CHANGES:
        if table not in tables:
            continue
        name = f"uq_{table}_tenant_company_{new_cols[-1]}"
        try:
            op.drop_constraint(name, table_name=table, type_="unique")
        except Exception:
            pass
        op.create_unique_constraint(f"uq_{table}_{'_'.join(old_cols)}", table, old_cols)
