"""POS device selling_online and offline_since for cashier presence.

Revision ID: 20261011_0138
Revises: 20261011_0137
Create Date: 2026-10-11

Adds the columns the cashier-presence list reads. Does not stamp or upgrade.
"""

import sqlalchemy as sa
from alembic import op

revision = "20261011_0138"
down_revision = "20261011_0137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pos_devices",
        sa.Column("selling_online", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "pos_devices",
        sa.Column("offline_since", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pos_devices", "offline_since")
    op.drop_column("pos_devices", "selling_online")
