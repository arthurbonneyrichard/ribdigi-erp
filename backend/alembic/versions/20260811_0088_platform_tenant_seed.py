"""Seed reserved Ribdigi House platform tenant (ADR-137)

Revision ID: 20260811_0088
Revises: 20260810_0087
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = "20260811_0088"
down_revision = "20260810_0087"
branch_labels = None
depends_on = None

PLATFORM_ID = "ribdigi-platform"


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        sa.text("SELECT 1 FROM tenants WHERE id = :id OR slug = :slug"),
        {"id": PLATFORM_ID, "slug": PLATFORM_ID},
    ).first()
    if exists:
        return
    now = datetime.utcnow()
    # Insert minimal columns that exist across versions; optional columns use defaults where present.
    cols = {r[1] for r in conn.execute(sa.text("PRAGMA table_info(tenants)")).fetchall()} if conn.dialect.name == "sqlite" else None
    # Prefer portable insert with core required fields + common optionals via raw SQL variants.
    if conn.dialect.name == "sqlite":
        conn.execute(
            sa.text(
                """
                INSERT INTO tenants (id, slug, company_name, industry, currency, status, created_at)
                VALUES (:id, :slug, :name, 'retail', 'USD', 'active', :created)
                """
            ),
            {
                "id": PLATFORM_ID,
                "slug": PLATFORM_ID,
                "name": "Ribdigi House",
                "created": now.isoformat(sep=" "),
            },
        )
        # Best-effort plan_code if column exists
        try:
            conn.execute(
                sa.text("UPDATE tenants SET plan_code = 'enterprise' WHERE id = :id"),
                {"id": PLATFORM_ID},
            )
        except Exception:
            pass
    else:
        # PostgreSQL — include plan_code when present
        conn.execute(
            sa.text(
                """
                INSERT INTO tenants (id, slug, company_name, industry, currency, status, plan_code, created_at)
                VALUES (:id, :slug, :name, 'retail', 'USD', 'active', 'enterprise', :created)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": PLATFORM_ID,
                "slug": PLATFORM_ID,
                "name": "Ribdigi House",
                "created": now,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    # Do not delete if platform users exist
    users = conn.execute(
        sa.text("SELECT 1 FROM users WHERE tenant_id = :id LIMIT 1"),
        {"id": PLATFORM_ID},
    ).first()
    if users:
        return
    conn.execute(sa.text("DELETE FROM tenants WHERE id = :id"), {"id": PLATFORM_ID})
