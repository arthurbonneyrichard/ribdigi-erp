"""Tenant books_closed_through for period close (BR-10.2).

Revision ID: 20260813_0079
Revises: 20260812_0078
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_0079"
down_revision = "20260812_0078"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("books_closed_through", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "books_closed_through")
