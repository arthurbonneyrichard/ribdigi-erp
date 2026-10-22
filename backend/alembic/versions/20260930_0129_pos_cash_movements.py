"""POS cash in/out movements and shift cash_in/cash_out totals.

Revision ID: 20260930_0129
Revises: 20260930_0128

Idempotent: skip column/table create when already present.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260930_0129"
down_revision = "20260930_0128"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "pos_sessions" in tables:
        cols = {c["name"] for c in insp.get_columns("pos_sessions")}
        if "cash_in" not in cols:
            op.add_column(
                "pos_sessions",
                sa.Column("cash_in", sa.Numeric(14, 2), nullable=False, server_default="0"),
            )
        if "cash_out" not in cols:
            op.add_column(
                "pos_sessions",
                sa.Column("cash_out", sa.Numeric(14, 2), nullable=False, server_default="0"),
            )

    if "pos_cash_movements" not in tables:
        op.create_table(
            "pos_cash_movements",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column(
                "session_id",
                sa.String(length=36),
                sa.ForeignKey("pos_sessions.id"),
                nullable=False,
            ),
            sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("movement_type", sa.String(length=20), nullable=False),
            sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(length=200), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        insp = sa.inspect(bind)

    if "pos_cash_movements" in set(insp.get_table_names()):
        existing_ix = {
            ix["name"] for ix in (insp.get_indexes("pos_cash_movements") or []) if ix.get("name")
        }
        for name, cols in (
            ("ix_pos_cash_movements_tenant_id", ["tenant_id"]),
            ("ix_pos_cash_movements_session_id", ["session_id"]),
            ("ix_pos_cash_movements_store_id", ["store_id"]),
            ("ix_pos_cash_movements_user_id", ["user_id"]),
            ("ix_pos_cash_movements_movement_type", ["movement_type"]),
        ):
            if name not in existing_ix:
                op.create_index(name, "pos_cash_movements", cols)


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "pos_cash_movements" in set(insp.get_table_names()):
        op.drop_table("pos_cash_movements")
    if "pos_sessions" in set(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns("pos_sessions")}
        if "cash_out" in cols:
            op.drop_column("pos_sessions", "cash_out")
        if "cash_in" in cols:
            op.drop_column("pos_sessions", "cash_in")
