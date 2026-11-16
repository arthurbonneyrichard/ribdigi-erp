"""Sign-in lockout ladder for staff and storefront shoppers, with timezone-aware times.

users: lockout start, last failed try, lockout step; ``locked_until`` becomes timestamptz.
ecommerce_shoppers: the same five lockout columns.

Revision ID: 20261116_0189
Revises: 20261115_0188
Create Date: 2026-11-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261116_0189"
down_revision = "20261115_0188"
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _to_timestamptz(table: str, column: str) -> None:
    # Existing values were written as naive UTC: read them as UTC, not as the server's zone.
    if _is_pg():
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamptz '
            f"USING CASE WHEN {column} IS NULL THEN NULL ELSE {column} AT TIME ZONE 'UTC' END"
        )


def _to_naive(table: str, column: str) -> None:
    if _is_pg():
        op.execute(
            f'ALTER TABLE {table} ALTER COLUMN {column} TYPE timestamp without time zone '
            f"USING CASE WHEN {column} IS NULL THEN NULL ELSE {column} AT TIME ZONE 'UTC' END"
        )


def _add_lockout_columns(table: str, *, with_counter: bool) -> None:
    cols = _columns(table)
    if with_counter and "failed_login_attempts" not in cols:
        op.add_column(table, sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"))
    if "locked_until" not in cols:
        op.add_column(table, sa.Column("locked_until", TZ, nullable=True))
    if "locked_at" not in cols:
        op.add_column(table, sa.Column("locked_at", TZ, nullable=True))
    if "last_failed_login_at" not in cols:
        op.add_column(table, sa.Column("last_failed_login_at", TZ, nullable=True))
    if "lockout_count" not in cols:
        op.add_column(table, sa.Column("lockout_count", sa.Integer(), nullable=False, server_default="0"))


def upgrade() -> None:
    had_locked_until = "locked_until" in _columns("users")
    _add_lockout_columns("users", with_counter=False)
    if had_locked_until:
        _to_timestamptz("users", "locked_until")
    # Admin screens list locked accounts; a small index beats a full users scan.
    if "ix_users_locked_until" not in _indexes("users"):
        op.create_index("ix_users_locked_until", "users", ["locked_until"])
    _add_lockout_columns("ecommerce_shoppers", with_counter=True)


def downgrade() -> None:
    cols = _columns("ecommerce_shoppers")
    for name in ("lockout_count", "last_failed_login_at", "locked_at", "locked_until", "failed_login_attempts"):
        if name in cols:
            op.drop_column("ecommerce_shoppers", name)
    if "ix_users_locked_until" in _indexes("users"):
        op.drop_index("ix_users_locked_until", table_name="users")
    _to_naive("users", "locked_until")
    cols = _columns("users")
    for name in ("lockout_count", "last_failed_login_at", "locked_at"):
        if name in cols:
            op.drop_column("users", name)
