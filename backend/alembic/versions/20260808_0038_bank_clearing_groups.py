"""bank clearing groups for many-to-one matches

Revision ID: 20260808_0038
Revises: 20260808_0037
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0038"
down_revision = "20260808_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_clearing_groups",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "statement_id",
            sa.String(length=36),
            sa.ForeignKey("bank_statements.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "bank_clearing_book_links",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("tenant_id", sa.String(length=36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "group_id",
            sa.String(length=36),
            sa.ForeignKey("bank_clearing_groups.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "journal_line_id",
            sa.String(length=36),
            sa.ForeignKey("journal_entry_lines.id"),
            nullable=False,
            unique=True,
        ),
    )
    op.add_column(
        "bank_statement_lines",
        sa.Column(
            "clearing_group_id",
            sa.String(length=36),
            sa.ForeignKey("bank_clearing_groups.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_bank_statement_lines_clearing_group_id",
        "bank_statement_lines",
        ["clearing_group_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_statement_lines_clearing_group_id", table_name="bank_statement_lines")
    op.drop_column("bank_statement_lines", "clearing_group_id")
    op.drop_table("bank_clearing_book_links")
    op.drop_table("bank_clearing_groups")
