"""Cash/bank transfers + account.bank_branch (BR-10.3).

Revision ID: 20260812_0072
Revises: 20260812_0071
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0072"
down_revision = "20260812_0071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("bank_branch", sa.String(length=120), nullable=True))
    op.create_table(
        "cash_transfers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="transfer"),
        sa.Column("from_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("to_account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("reference", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("journal_entry_id", sa.String(length=36), sa.ForeignKey("journal_entries.id"), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_cash_transfers_tenant_id", "cash_transfers", ["tenant_id"])
    op.create_index("ix_cash_transfers_from_account_id", "cash_transfers", ["from_account_id"])
    op.create_index("ix_cash_transfers_to_account_id", "cash_transfers", ["to_account_id"])


def downgrade() -> None:
    op.drop_index("ix_cash_transfers_to_account_id", table_name="cash_transfers")
    op.drop_index("ix_cash_transfers_from_account_id", table_name="cash_transfers")
    op.drop_index("ix_cash_transfers_tenant_id", table_name="cash_transfers")
    op.drop_table("cash_transfers")
    op.drop_column("accounts", "bank_branch")
