"""Scheduled daily backups on by default.

Companies whose backup settings are still exactly the untouched defaults (off, daily, 02:00 UTC,
keep 30) never chose anything, so their daily backup is turned on. A company whose admin changed
any setting keeps its choice.

Revision ID: 20261114_0182
Revises: 20261114_0181
Create Date: 2026-11-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261114_0182"
down_revision = "20261114_0181"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE backup_settings SET enabled = :on "
            "WHERE enabled = :off AND frequency = 'daily' AND hour_utc = 2 AND retention_count = 30"
        ).bindparams(on=True, off=False)
    )


def downgrade() -> None:
    # Which companies were switched on here is not recorded; leave the settings as they are.
    pass
