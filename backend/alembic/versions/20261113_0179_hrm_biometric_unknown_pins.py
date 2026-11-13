"""HRM ZKTeco links remember terminal PINs that match no staff record.

Revision ID: 20261113_0179
Revises: 20261113_0178
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261113_0179"
down_revision = "20261113_0178"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("hrm_biometric_links") as batch:
        batch.add_column(sa.Column("unknown_pins", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hrm_biometric_links") as batch:
        batch.drop_column("unknown_pins")
