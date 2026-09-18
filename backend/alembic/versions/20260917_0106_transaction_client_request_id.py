"""Add client_request_id for POS sale idempotency (offline sync).

Revision ID: 20260917_0106
Revises: 20260917_0105
Create Date: 2026-09-17

Production-safe / idempotent:
Earlier production lineage already added transactions.client_request_id
(and related indexes/constraints). This revision must not fail with
DuplicateColumn / DuplicateTable when those objects already exist.
Incompatible existing column types raise instead of being silently accepted.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260917_0106"
down_revision = "20260917_0105"
branch_labels = None
depends_on = None

_EXPECTED_MIN_LENGTH = 64


def _pg_column_info(bind, table: str, column: str) -> dict | None:
    """Return information_schema row for table.column, or None if missing."""
    row = bind.execute(
        sa.text(
            """
            SELECT data_type, character_maximum_length, is_nullable, udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).mappings().first()
    return dict(row) if row else None


def _pg_index_exists(bind, index_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relkind IN ('i', 'I')
                  AND c.relname = :name
                  AND n.nspname = current_schema()
                """
            ),
            {"name": index_name},
        ).scalar()
    )


def _pg_constraint_exists(bind, constraint_name: str) -> bool:
    return bool(
        bind.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                WHERE c.conname = :name
                  AND n.nspname = current_schema()
                """
            ),
            {"name": constraint_name},
        ).scalar()
    )


def _pg_has_unique_on_cols(bind, table: str, cols: list[str]) -> bool:
    """True if a unique constraint or unique index covers exactly these columns."""
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_index i
            JOIN pg_class t ON t.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE t.relname = :table
              AND n.nspname = current_schema()
              AND i.indisunique
              AND (
                SELECT array_agg(a.attname::text ORDER BY x.ordinality)
                FROM unnest(i.indkey) WITH ORDINALITY AS x(attnum, ordinality)
                JOIN pg_attribute a
                  ON a.attrelid = t.oid AND a.attnum = x.attnum
              ) = CAST(:cols AS text[])
            LIMIT 1
            """
        ),
        {"table": table, "cols": cols},
    ).scalar()
    return bool(row)


def _assert_compatible_client_request_id(info: dict) -> None:
    """Raise if an existing column cannot satisfy String(64) nullable semantics."""
    data_type = (info.get("data_type") or "").lower()
    udt = (info.get("udt_name") or "").lower()
    ok_types = {"character varying", "varchar", "text", "character"}
    if data_type not in ok_types and udt not in {"varchar", "text", "bpchar"}:
        raise RuntimeError(
            "transactions.client_request_id already exists with incompatible type "
            f"{info.get('data_type')!r} (udt={info.get('udt_name')!r}); "
            f"expected VARCHAR/TEXT nullable string (min length {_EXPECTED_MIN_LENGTH})"
        )
    max_len = info.get("character_maximum_length")
    # TEXT has NULL length; VARCHAR(n) with n < 64 cannot hold app values up to 64.
    if max_len is not None and int(max_len) < _EXPECTED_MIN_LENGTH:
        raise RuntimeError(
            "transactions.client_request_id already exists with insufficient length "
            f"{max_len} (need >= {_EXPECTED_MIN_LENGTH}); refusing to silently alter"
        )


def _upgrade_postgresql(bind) -> None:
    info = _pg_column_info(bind, "transactions", "client_request_id")
    if info is None:
        bind.execute(
            sa.text(
                "ALTER TABLE transactions "
                "ADD COLUMN IF NOT EXISTS client_request_id VARCHAR(64)"
            )
        )
    else:
        _assert_compatible_client_request_id(info)

    # Non-unique supporting index (same name used historically).
    if not _pg_index_exists(bind, "ix_transactions_client_request_id"):
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_client_request_id "
                "ON transactions (client_request_id)"
            )
        )

    # Partial unique for non-null client_request_id values.
    # Skip when this name, an equivalent unique, or the company-scoped unique exists.
    if (
        not _pg_index_exists(bind, "uq_transactions_tenant_client_request")
        and not _pg_constraint_exists(bind, "uq_transactions_tenant_client_request")
        and not _pg_constraint_exists(bind, "uq_transactions_tenant_client_request_id")
        and not _pg_index_exists(bind, "uq_transactions_tenant_client_request_id")
        and not _pg_index_exists(bind, "uq_transactions_tenant_company_client_request_id")
        and not _pg_has_unique_on_cols(bind, "transactions", ["tenant_id", "client_request_id"])
    ):
        bind.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_tenant_client_request
                ON transactions (tenant_id, client_request_id)
                WHERE client_request_id IS NOT NULL
                """
            )
        )


def _upgrade_other(bind) -> None:
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("transactions")}
    indexes = {ix["name"] for ix in (insp.get_indexes("transactions") or []) if ix.get("name")}
    uniques = {
        uq["name"] for uq in (insp.get_unique_constraints("transactions") or []) if uq.get("name")
    }

    if "client_request_id" not in cols:
        op.add_column(
            "transactions",
            sa.Column("client_request_id", sa.String(length=64), nullable=True),
        )
    else:
        # Best-effort type gate for non-Postgres dialects used in tests.
        col = next(c for c in insp.get_columns("transactions") if c["name"] == "client_request_id")
        col_type = col.get("type")
        if col_type is not None and not isinstance(col_type, (sa.String, sa.Text)):
            raise RuntimeError(
                "transactions.client_request_id already exists with incompatible type "
                f"{col_type!r}"
            )

    if "ix_transactions_client_request_id" not in indexes:
        op.create_index(
            "ix_transactions_client_request_id",
            "transactions",
            ["client_request_id"],
        )

    if "uq_transactions_tenant_client_request" not in indexes | uniques:
        already = False
        for uq in insp.get_unique_constraints("transactions") or []:
            if set(uq.get("column_names") or []) == {"tenant_id", "client_request_id"}:
                already = True
                break
        for ix in insp.get_indexes("transactions") or []:
            if ix.get("unique") and set(ix.get("column_names") or []) == {
                "tenant_id",
                "client_request_id",
            }:
                already = True
                break
        if not already:
            op.create_unique_constraint(
                "uq_transactions_tenant_client_request",
                "transactions",
                ["tenant_id", "client_request_id"],
            )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _upgrade_postgresql(bind)
    else:
        _upgrade_other(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DROP INDEX IF EXISTS uq_transactions_tenant_client_request"))
        bind.execute(sa.text("DROP INDEX IF EXISTS ix_transactions_client_request_id"))
        info = _pg_column_info(bind, "transactions", "client_request_id")
        if info is not None:
            # Only drop if we would own a VARCHAR(64) column; leave longer legacy columns.
            max_len = info.get("character_maximum_length")
            if max_len is None or int(max_len) == _EXPECTED_MIN_LENGTH:
                bind.execute(sa.text("ALTER TABLE transactions DROP COLUMN IF EXISTS client_request_id"))
        return

    insp = sa.inspect(bind)
    indexes = {ix["name"] for ix in (insp.get_indexes("transactions") or []) if ix.get("name")}
    uniques = {
        uq["name"] for uq in (insp.get_unique_constraints("transactions") or []) if uq.get("name")
    }
    cols = {c["name"] for c in insp.get_columns("transactions")}
    if "uq_transactions_tenant_client_request" in indexes | uniques:
        op.drop_constraint(
            "uq_transactions_tenant_client_request",
            "transactions",
            type_="unique",
        )
    if "ix_transactions_client_request_id" in indexes:
        op.drop_index("ix_transactions_client_request_id", table_name="transactions")
    if "client_request_id" in cols:
        op.drop_column("transactions", "client_request_id")
