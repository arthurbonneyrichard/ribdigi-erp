"""A browser session opened at a till with a passcode is limited to the till and Sales.

Revision ID: 20261112_0160
Revises: 20261109_0159
Create Date: 2026-11-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20261112_0160"
down_revision = "20261109_0159"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("auth_sessions")}
    if "till_only" not in columns:
        op.add_column(
            "auth_sessions",
            sa.Column("till_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    columns = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("auth_sessions")}
    if "till_only" in columns:
        op.drop_column("auth_sessions", "till_only")
