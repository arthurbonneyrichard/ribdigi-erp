"""Gym: which channels get the daily renewal reminder (off by default).

Revision ID: 20261119_0211g
Revises: 20261119_0210g
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0211g"
down_revision = "20261119_0210g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gym_settings", sa.Column("reminder_channels", sa.String(10), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("gym_settings", "reminder_channels")
