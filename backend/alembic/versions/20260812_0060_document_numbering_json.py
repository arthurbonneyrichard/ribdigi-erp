"""document numbering JSON for PO/GRN/quotation series

Revision ID: 20260812_0060
Revises: 20260812_0059
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260812_0060"
down_revision = "20260812_0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("document_numbering", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "document_numbering")
