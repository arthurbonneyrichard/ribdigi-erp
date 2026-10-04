"""Reactivate Ribdigi House platform tenant and set contact email.

Revision ID: 20260920_0114
Revises: 20260920_0113
Create Date: 2026-09-20

Ops recovery: platform workspace was mistakenly suspended, which blocked all
platform_owner logins (chicken-and-egg). Idempotent activate + email update.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260920_0114"
down_revision = "20260920_0113"
branch_labels = None
depends_on = None

_TARGET_EMAIL = "info@ribdigihouse.com"


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE tenants
            SET
                status = 'active',
                email = :email,
                suspended_at = NULL,
                suspended_reason = NULL,
                grace_ends_at = NULL
            WHERE
                slug IN ('platform', 'ribdigi-platform')
                OR lower(company_name) = lower('Ribdigi House')
                OR id IN ('platform', 'ribdigi-platform')
            """
        ),
        {"email": _TARGET_EMAIL},
    )


def downgrade() -> None:
    # Do not re-suspend; only clear the contact email we set if it still matches.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE tenants
            SET email = NULL
            WHERE email = :email
              AND (
                slug IN ('platform', 'ribdigi-platform')
                OR lower(company_name) = lower('Ribdigi House')
                OR id IN ('platform', 'ribdigi-platform')
              )
            """
        ),
        {"email": _TARGET_EMAIL},
    )
