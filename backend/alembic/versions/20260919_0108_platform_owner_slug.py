"""Rename platform owner workspace slug to platform.

Revision ID: 20260919_0108
Revises: 20260917_0107
Create Date: 2026-09-19

Updates existing slug ribdigi-platform → platform.
Does not change tenants.id (JWT and foreign keys stay valid).
Skips if slug platform is already used by another tenant.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260919_0108"
down_revision = "20260917_0107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    taken = conn.execute(
        sa.text("SELECT id FROM tenants WHERE slug = 'platform' LIMIT 1")
    ).fetchone()
    if taken is not None:
        return
    conn.execute(
        sa.text(
            "UPDATE tenants SET slug = 'platform' WHERE slug = 'ribdigi-platform'"
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    taken = conn.execute(
        sa.text("SELECT id FROM tenants WHERE slug = 'ribdigi-platform' LIMIT 1")
    ).fetchone()
    if taken is not None:
        return
    conn.execute(
        sa.text(
            "UPDATE tenants SET slug = 'ribdigi-platform' "
            "WHERE slug = 'platform' AND id = 'ribdigi-platform'"
        )
    )
