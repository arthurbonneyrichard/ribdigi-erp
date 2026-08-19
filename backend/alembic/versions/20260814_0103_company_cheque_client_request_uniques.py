"""ADR-490 phase 21 — company-scoped cheque and POS client_request_id uniques.

Revision ID: 20260814_0103
Revises: 20260814_0102
Create Date: 2026-08-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260814_0103"
down_revision = "20260814_0102"
branch_labels = None
depends_on = None


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


def _backfill_company(table: str) -> None:
    op.execute(
        sa.text(
            f"UPDATE {table} SET company_id = ("
            f"SELECT c.id FROM companies c WHERE c.tenant_id = {table}.tenant_id "
            f"AND c.is_default = true LIMIT 1) "
            f"WHERE company_id IS NULL"
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "cheques" in tables:
        cols = {c["name"] for c in insp.get_columns("cheques")}
        if "company_id" in cols:
            _backfill_company("cheques")
            _drop_matching_unique(insp, "cheques", ["tenant_id", "cheque_number", "direction"])
            op.create_unique_constraint(
                "uq_cheques_tenant_company_cheque_number_direction",
                "cheques",
                ["tenant_id", "company_id", "cheque_number", "direction"],
            )

    if "transactions" in tables:
        cols = {c["name"] for c in insp.get_columns("transactions")}
        if "company_id" in cols and "client_request_id" in cols:
            _backfill_company("transactions")
            _drop_matching_unique(insp, "transactions", ["tenant_id", "client_request_id"])
            # Partial unique so legacy online sales with NULL client_request_id remain valid.
            op.execute(
                sa.text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_transactions_tenant_company_client_request_id "
                    "ON transactions (tenant_id, company_id, client_request_id) "
                    "WHERE client_request_id IS NOT NULL"
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "transactions" in tables:
        op.execute(
            sa.text("DROP INDEX IF EXISTS uq_transactions_tenant_company_client_request_id")
        )
        op.create_unique_constraint(
            "uq_transactions_tenant_client_request_id",
            "transactions",
            ["tenant_id", "client_request_id"],
        )

    if "cheques" in tables:
        try:
            op.drop_constraint(
                "uq_cheques_tenant_company_cheque_number_direction",
                table_name="cheques",
                type_="unique",
            )
        except Exception:
            pass
        op.create_unique_constraint(
            "uq_cheques_tenant_num_dir",
            "cheques",
            ["tenant_id", "cheque_number", "direction"],
        )
