"""Gym fees: guest fee on a visit, locker rental end date.

Revision ID: 20261119_0205g
Revises: 20261119_0204h
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0205g"
down_revision = "20261119_0204h"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gym_guest_visits", sa.Column("fee", sa.Numeric(14, 2), nullable=False, server_default="0"))
    op.add_column("gym_lockers", sa.Column("rented_until", sa.Date()))
    op.create_index("ix_gym_lockers_rented_until", "gym_lockers", ["rented_until"])


def downgrade() -> None:
    op.drop_index("ix_gym_lockers_rented_until", "gym_lockers")
    op.drop_column("gym_lockers", "rented_until")
    op.drop_column("gym_guest_visits", "fee")
