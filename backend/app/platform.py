"""Platform Owner services — Ribdigi House SaaS console (ADR-137)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import tenants as tenants_svc
from app.platform_const import (
    PLATFORM_COMPANY_NAME,
    PLATFORM_TENANT_ID,
    PLATFORM_TENANT_SLUG,
)


async def ensure_platform_tenant(db: AsyncSession) -> m.Tenant:
    """Idempotent reserved platform tenant for tests and runtime."""
    row = await db.get(m.Tenant, PLATFORM_TENANT_ID)
    if row:
        return row
    by_slug = (
        await db.execute(select(m.Tenant).where(m.Tenant.slug == PLATFORM_TENANT_SLUG))
    ).scalar_one_or_none()
    if by_slug:
        return by_slug
    row = m.Tenant(
        id=PLATFORM_TENANT_ID,
        slug=PLATFORM_TENANT_SLUG,
        company_name=PLATFORM_COMPANY_NAME,
        industry="retail",
        currency="USD",
        status="active",
        plan_code="enterprise",
    )
    db.add(row)
    await db.flush()
    return row


def assert_not_reserved_tenant_slug(slug: str) -> None:
    value = (slug or "").strip().lower()
    if value in {PLATFORM_TENANT_SLUG, PLATFORM_TENANT_ID, "ribdigi", "ribdigi-house"}:
        raise HTTPException(
            status_code=400,
            detail="Tenant slug is reserved for Ribdigi House platform administration",
        )


def _customer_tenant_filter():
    return m.Tenant.id != PLATFORM_TENANT_ID


async def platform_dashboard_kpis(db: AsyncSession) -> dict:
    """Real aggregates over customer tenants only — no fabricated revenue."""
    await ensure_platform_tenant(db)
    status_rows = (
        await db.execute(
            select(m.Tenant.status, func.count())
            .where(_customer_tenant_filter())
            .group_by(m.Tenant.status)
        )
    ).all()
    by_status = {str(s or ""): int(c) for s, c in status_rows}
    total = sum(by_status.values())
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)
    new_this_month = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.Tenant)
                .where(
                    _customer_tenant_filter(),
                    m.Tenant.created_at >= month_start,
                )
            )
        ).scalar_one()
        or 0
    )
    platform_users = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.User)
                .where(m.User.tenant_id == PLATFORM_TENANT_ID, m.User.is_active == True)  # noqa: E712
            )
        ).scalar_one()
        or 0
    )
    customer_users = int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.User)
                .join(m.Tenant, m.Tenant.id == m.User.tenant_id)
                .where(m.Tenant.id != PLATFORM_TENANT_ID)
            )
        ).scalar_one()
        or 0
    )
    return {
        "total_tenants": total,
        "active_tenants": by_status.get("active", 0),
        "trial_tenants": by_status.get("trial", 0),
        "grace_tenants": by_status.get("grace", 0),
        "suspended_tenants": by_status.get("suspended", 0),
        "new_tenants_this_month": new_this_month,
        "platform_users": platform_users,
        "customer_users": customer_users,
        "status_breakdown": by_status,
        "billing": {
            "deferred": True,
            "provider": None,
            "mrr": None,
            "outstanding_payments": None,
            "active_subscriptions": None,
            "message": "Subscription billing is deferred (ADR-002). Plan codes are metadata only.",
        },
        "generated_at": now.isoformat() + "Z",
    }


async def _enrich_tenant_row(db: AsyncSession, t: m.Tenant) -> dict:
    user_count = int(
        (
            await db.execute(
                select(func.count()).select_from(m.User).where(m.User.tenant_id == t.id)
            )
        ).scalar_one()
        or 0
    )
    store_count = int(
        (
            await db.execute(
                select(func.count()).select_from(m.Store).where(m.Store.tenant_id == t.id)
            )
        ).scalar_one()
        or 0
    )
    branch_count = 0
    if hasattr(m, "Branch"):
        branch_count = int(
            (
                await db.execute(
                    select(func.count()).select_from(m.Branch).where(m.Branch.tenant_id == t.id)
                )
            ).scalar_one()
            or 0
        )
    last_activity = (
        await db.execute(
            select(func.max(m.AuditLog.created_at)).where(m.AuditLog.tenant_id == t.id)
        )
    ).scalar_one()
    base = tenants_svc.serialize_tenant(t)
    base.update(
        {
            "user_count": user_count,
            "store_count": store_count,
            "branch_count": branch_count,
            "last_activity_at": last_activity.isoformat() + "Z" if last_activity else None,
        }
    )
    return base


async def list_customer_tenants(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    await ensure_platform_tenant(db)
    filters = [_customer_tenant_filter()]
    if status:
        filters.append(m.Tenant.status == status)
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        filters.append(
            or_(
                func.lower(m.Tenant.slug).like(like),
                func.lower(m.Tenant.company_name).like(like),
                m.Tenant.id == q.strip(),
            )
        )
    total = int(
        (
            await db.execute(select(func.count()).select_from(m.Tenant).where(*filters))
        ).scalar_one()
        or 0
    )
    rows = (
        await db.execute(
            select(m.Tenant)
            .where(*filters)
            .order_by(m.Tenant.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    out: list[dict] = []
    for t in rows:
        out.append(await _enrich_tenant_row(db, t))
    return out, total


async def get_customer_tenant(db: AsyncSession, tenant_ref: str) -> dict | None:
    try:
        tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    except HTTPException:
        return None
    if tenant.id == PLATFORM_TENANT_ID:
        return None
    return await _enrich_tenant_row(db, tenant)
