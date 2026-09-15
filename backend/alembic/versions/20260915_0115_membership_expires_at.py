"""ADR-005 temp membership expires_at (PARTIAL — elevation/break-glass MISSING).

Revision ID: 20260915_0115
Revises: 20260914_0114
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260915_0115"
down_revision = "20260914_0114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_store_memberships",
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_user_store_memberships_expires_at",
        "user_store_memberships",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_store_memberships_expires_at",
        table_name="user_store_memberships",
    )
    op.drop_column("user_store_memberships", "expires_at")
