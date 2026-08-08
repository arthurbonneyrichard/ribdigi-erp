"""tenant expense_approval_matrix JSON

Revision ID: 20260808_0040
Revises: 20260808_0039
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0040"
down_revision = "20260808_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("expense_approval_matrix", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "expense_approval_matrix")
