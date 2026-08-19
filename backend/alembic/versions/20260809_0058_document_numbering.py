"""Tenant document numbering prefix and series

Revision ID: 20260809_0058
Revises: 20260809_0057
Create Date: 2026-08-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260809_0058"
down_revision = "20260809_0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.add_column(sa.Column("document_numbering", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tenants") as batch:
        batch.drop_column("document_numbering")
