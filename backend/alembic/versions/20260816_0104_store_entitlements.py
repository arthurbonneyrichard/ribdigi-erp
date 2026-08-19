"""Company store_limit + Tenant max_stores_override for subscription multi-store.

Revision ID: 20260816_0104
Revises: 20260814_0103
Create Date: 2026-08-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260816_0104"
down_revision = "20260814_0103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("max_stores_override", sa.Integer(), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("store_limit", sa.Integer(), nullable=True),
    )

    # Backfill: each company gets store_limit = max(active store count, 0).
    # Default company additionally receives remaining tenant capacity so
    # existing single-company tenants keep working without manual allocation.
    conn = op.get_bind()
    companies = conn.execute(
        sa.text("SELECT id, tenant_id, is_default FROM companies")
    ).fetchall()
    for cid, tid, is_default in companies:
        used = conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM stores "
                "WHERE tenant_id = :tid AND company_id = :cid AND is_active = true"
            ),
            {"tid": tid, "cid": cid},
        ).scalar()
        used = int(used or 0)
        conn.execute(
            sa.text("UPDATE companies SET store_limit = :lim WHERE id = :cid"),
            {"lim": used, "cid": cid},
        )

    tenants = conn.execute(
        sa.text("SELECT id, max_stores FROM tenants")
    ).fetchall()
    for tid, max_stores in tenants:
        max_stores = int(max_stores if max_stores is not None else 5)
        if max_stores < 0:
            # Unlimited tenant: leave company allocations as usage-based.
            continue
        allocated = conn.execute(
            sa.text(
                "SELECT COALESCE(SUM(store_limit), 0) FROM companies "
                "WHERE tenant_id = :tid AND is_active = true AND store_limit IS NOT NULL "
                "AND store_limit >= 0"
            ),
            {"tid": tid},
        ).scalar()
        allocated = int(allocated or 0)
        remaining = max(0, max_stores - allocated)
        if remaining <= 0:
            continue
        default = conn.execute(
            sa.text(
                "SELECT id FROM companies "
                "WHERE tenant_id = :tid AND is_default = true LIMIT 1"
            ),
            {"tid": tid},
        ).fetchone()
        if not default:
            default = conn.execute(
                sa.text(
                    "SELECT id FROM companies WHERE tenant_id = :tid "
                    "ORDER BY created_at ASC LIMIT 1"
                ),
                {"tid": tid},
            ).fetchone()
        if default:
            conn.execute(
                sa.text(
                    "UPDATE companies SET store_limit = COALESCE(store_limit, 0) + :extra "
                    "WHERE id = :cid"
                ),
                {"extra": remaining, "cid": default[0]},
            )


def downgrade() -> None:
    op.drop_column("companies", "store_limit")
    op.drop_column("tenants", "max_stores_override")
