"""Gym settings: manager switches (insights on/off).

Revision ID: 20261119_0200
Revises: 20261119_0199
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261119_0200"
down_revision = "20261119_0199"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gym_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, unique=True, index=True),
        sa.Column("insights_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("gym_settings")
