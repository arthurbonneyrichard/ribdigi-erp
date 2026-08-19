"""ADR-490 phase 15 — company-scoped org/catalog/party uniqueness.

Revision ID: 20260814_0098
Revises: 20260814_0097
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260814_0098"
down_revision = "20260814_0097"
branch_labels = None
depends_on = None

# (table, old_unique_cols, new_unique_cols)
CHANGES = [
    ("branches", ["tenant_id", "code"], ["tenant_id", "company_id", "code"]),
    ("departments", ["tenant_id", "code"], ["tenant_id", "company_id", "code"]),
    ("stores", ["tenant_id", "code"], ["tenant_id", "company_id", "code"]),
    ("product_variants", ["tenant_id", "sku"], ["tenant_id", "company_id", "sku"]),
    ("parties", ["tenant_id", "kind", "code"], ["tenant_id", "company_id", "kind", "code"]),
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
    for table, old_cols, new_cols in CHANGES:
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
        suffix = new_cols[-1]
        op.create_unique_constraint(
            f"uq_{table}_tenant_company_{suffix}",
            table,
            new_cols,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    for table, old_cols, new_cols in CHANGES:
        if table not in tables:
            continue
        name = f"uq_{table}_tenant_company_{new_cols[-1]}"
        try:
            op.drop_constraint(name, table_name=table, type_="unique")
        except Exception:
            pass
        op.create_unique_constraint(f"uq_{table}_{'_'.join(old_cols)}", table, old_cols)
