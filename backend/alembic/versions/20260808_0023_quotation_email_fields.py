"""quotation email delivery fields

Revision ID: 20260808_0023
Revises: 20260808_0022
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260808_0023"
down_revision = "20260808_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sales_quotations", sa.Column("emailed_at", sa.DateTime(), nullable=True))
    op.add_column("sales_quotations", sa.Column("emailed_to", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_quotations", "emailed_to")
    op.drop_column("sales_quotations", "emailed_at")
