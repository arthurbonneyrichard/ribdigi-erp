"""POS sessions tables and transaction.session_id

Revision ID: 20260808_0005
Revises: 20260808_0004
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0005"
down_revision = "20260808_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pos_sessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("store_id", sa.String(length=36), sa.ForeignKey("stores.id"), nullable=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("opening_cash", sa.Numeric(14, 2), nullable=False),
        sa.Column("expected_cash", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_cash", sa.Numeric(14, 2), nullable=True),
        sa.Column("cash_sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("card_sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("other_sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_sales", sa.Numeric(14, 2), nullable=False),
        sa.Column("sale_count", sa.Integer(), nullable=False),
        sa.Column("variance", sa.Numeric(14, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("tenant_id", "session_number"),
    )
    op.create_index("ix_pos_sessions_tenant_id", "pos_sessions", ["tenant_id"])
    op.create_index("ix_pos_sessions_user_id", "pos_sessions", ["user_id"])
    op.create_index("ix_pos_sessions_status", "pos_sessions", ["status"])

    op.add_column(
        "transactions",
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("pos_sessions.id"), nullable=True),
    )
    op.create_index("ix_transactions_session_id", "transactions", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_session_id", table_name="transactions")
    op.drop_column("transactions", "session_id")
    op.drop_table("pos_sessions")
