"""journal entries tables

Revision ID: 20260808_0004
Revises: 20260808_0003
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0004"
down_revision = "20260808_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("entry_number", sa.String(length=50), nullable=False),
        sa.Column("entry_date", sa.DateTime(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("total_debit", sa.Numeric(14, 2), nullable=False),
        sa.Column("total_credit", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "entry_number"),
    )
    op.create_index("ix_journal_entries_tenant_id", "journal_entries", ["tenant_id"])

    op.create_table(
        "journal_entry_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("journal_entry_id", sa.String(length=36), sa.ForeignKey("journal_entries.id"), nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("ix_journal_entry_lines_entry", "journal_entry_lines", ["journal_entry_id"])


def downgrade() -> None:
    op.drop_table("journal_entry_lines")
    op.drop_table("journal_entries")
