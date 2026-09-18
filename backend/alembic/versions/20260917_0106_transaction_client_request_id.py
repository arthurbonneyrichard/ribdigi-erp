"""Add client_request_id for POS sale idempotency (offline sync).

Revision ID: 20260917_0106
Revises: 20260917_0105
Create Date: 2026-09-17

Idempotent on PostgreSQL: production DBs that previously ran main's
20260813_0092 (sync_queue_and_pos_idempotency) already have
transactions.client_request_id and related indexes/constraints.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260917_0106"
down_revision = "20260917_0105"
branch_labels = None
depends_on = None


def _column_names(insp: sa.Inspector, table: str) -> set[str]:
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(insp: sa.Inspector, table: str) -> set[str]:
    names: set[str] = set()
    for ix in insp.get_indexes(table) or []:
        if ix.get("name"):
            names.add(ix["name"])
    # Unique constraints appear separately from indexes on PostgreSQL.
    for uq in insp.get_unique_constraints(table) or []:
        if uq.get("name"):
            names.add(uq["name"])
    return names


def _has_unique_on_cols(insp: sa.Inspector, table: str, cols: set[str]) -> bool:
    want = set(cols)
    for uq in insp.get_unique_constraints(table) or []:
        if set(uq.get("column_names") or []) == want:
            return True
    for ix in insp.get_indexes(table) or []:
        if ix.get("unique") and set(ix.get("column_names") or []) == want:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = _column_names(insp, "transactions")
    existing = _index_names(insp, "transactions")

    if "client_request_id" not in cols:
        op.add_column(
            "transactions",
            sa.Column("client_request_id", sa.String(length=64), nullable=True),
        )
        # Refresh inspector view after DDL.
        insp = sa.inspect(bind)
        existing = _index_names(insp, "transactions")

    if "ix_transactions_client_request_id" not in existing:
        op.create_index(
            "ix_transactions_client_request_id",
            "transactions",
            ["client_request_id"],
        )
        insp = sa.inspect(bind)
        existing = _index_names(insp, "transactions")

    # Partial unique: only when client_request_id is set (Postgres).
    # SQLite tests use create_all from models UniqueConstraint.
    # Skip if this index/constraint name already exists, or an equivalent
    # unique on (tenant_id, client_request_id) is already present (e.g. from
    # main's uq_transactions_tenant_client_request_id).
    if bind.dialect.name == "postgresql":
        if (
            "uq_transactions_tenant_client_request" not in existing
            and not _has_unique_on_cols(
                insp, "transactions", {"tenant_id", "client_request_id"}
            )
        ):
            # Also skip when a stricter company-scoped partial unique already
            # covers idempotency (main ADR-490 phase 21).
            if "uq_transactions_tenant_company_client_request_id" not in existing:
                op.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_tenant_client_request
                    ON transactions (tenant_id, client_request_id)
                    WHERE client_request_id IS NOT NULL
                    """
                )
    else:
        if "uq_transactions_tenant_client_request" not in existing and not _has_unique_on_cols(
            insp, "transactions", {"tenant_id", "client_request_id"}
        ):
            op.create_unique_constraint(
                "uq_transactions_tenant_client_request",
                "transactions",
                ["tenant_id", "client_request_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = _index_names(insp, "transactions")
    cols = _column_names(insp, "transactions")

    if bind.dialect.name == "postgresql":
        if "uq_transactions_tenant_client_request" in existing:
            op.execute("DROP INDEX IF EXISTS uq_transactions_tenant_client_request")
    else:
        if "uq_transactions_tenant_client_request" in existing:
            op.drop_constraint(
                "uq_transactions_tenant_client_request",
                "transactions",
                type_="unique",
            )

    if "ix_transactions_client_request_id" in existing:
        op.drop_index("ix_transactions_client_request_id", table_name="transactions")
    if "client_request_id" in cols:
        op.drop_column("transactions", "client_request_id")
