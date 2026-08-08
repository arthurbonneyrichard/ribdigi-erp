"""bank reconciliation tables and account liquid flags

Revision ID: 20260808_0028
Revises: 20260808_0027
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0028"
down_revision = "20260808_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("is_cash_account", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "accounts",
        sa.Column("is_bank_account", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("accounts", sa.Column("bank_name", sa.String(length=120), nullable=True))
    op.add_column("accounts", sa.Column("account_number", sa.String(length=60), nullable=True))

    op.create_table(
        "bank_statements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("statement_date", sa.DateTime(), nullable=False),
        sa.Column("opening_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("closing_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_bank_statements_tenant_id", "bank_statements", ["tenant_id"])
    op.create_index("ix_bank_statements_account_id", "bank_statements", ["account_id"])

    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "statement_id",
            sa.String(length=36),
            sa.ForeignKey("bank_statements.id"),
            nullable=False,
        ),
        sa.Column("txn_date", sa.DateTime(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="unmatched"),
        sa.Column(
            "matched_journal_line_id",
            sa.String(length=36),
            sa.ForeignKey("journal_entry_lines.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_bank_statement_lines_tenant_id", "bank_statement_lines", ["tenant_id"])
    op.create_index("ix_bank_statement_lines_statement_id", "bank_statement_lines", ["statement_id"])
    op.create_index(
        "ix_bank_statement_lines_matched_journal_line_id",
        "bank_statement_lines",
        ["matched_journal_line_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_statement_lines_matched_journal_line_id", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_statement_id", table_name="bank_statement_lines")
    op.drop_index("ix_bank_statement_lines_tenant_id", table_name="bank_statement_lines")
    op.drop_table("bank_statement_lines")
    op.drop_index("ix_bank_statements_account_id", table_name="bank_statements")
    op.drop_index("ix_bank_statements_tenant_id", table_name="bank_statements")
    op.drop_table("bank_statements")
    op.drop_column("accounts", "account_number")
    op.drop_column("accounts", "bank_name")
    op.drop_column("accounts", "is_bank_account")
    op.drop_column("accounts", "is_cash_account")
