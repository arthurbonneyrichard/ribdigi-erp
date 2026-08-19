"""Sales return credit note number

Revision ID: 20260809_0063
Revises: 20260809_0062
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0063"
down_revision = "20260809_0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sales_returns") as batch:
        batch.add_column(sa.Column("credit_note_number", sa.String(length=50), nullable=True))
        batch.create_index("ix_sales_returns_credit_note_number", ["credit_note_number"])


def downgrade() -> None:
    with op.batch_alter_table("sales_returns") as batch:
        batch.drop_index("ix_sales_returns_credit_note_number")
        batch.drop_column("credit_note_number")
