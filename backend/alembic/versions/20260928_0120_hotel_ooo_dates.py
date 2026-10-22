"""Hotel maintenance out-of-order date range.

Revision ID: 20260928_0120
Revises: 20260928_0119
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260928_0120"
down_revision = "20260928_0119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("hotel_maintenance_tickets", sa.Column("ooo_starts_on", sa.Date(), nullable=True))
    op.add_column("hotel_maintenance_tickets", sa.Column("ooo_ends_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("hotel_maintenance_tickets", "ooo_ends_on")
    op.drop_column("hotel_maintenance_tickets", "ooo_starts_on")
