"""Cross-tenant platform reports for software-owner staff."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import packages as packages_svc
from app import tenants as tenants_svc


async def build_platform_summary(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(m.Tenant).order_by(m.Tenant.created_at.desc()))).scalars().all()
    by_status: dict[str, int] = {}
    by_package: dict[str, int] = {}
    for t in rows:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        code = getattr(t, "package_code", None) or "trial"
        by_package[code] = by_package.get(code, 0) + 1
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "tenant_count": len(rows),
        "by_status": by_status,
        "by_package": by_package,
    }


async def build_subscription_usage_report(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(m.Tenant).order_by(m.Tenant.company_name.asc()))).scalars().all()
    items = []
    for t in rows:
        usage = packages_svc.usage_snapshot(t)
        items.append(
            {
                "tenant_id": t.id,
                "slug": t.slug,
                "company_name": t.company_name,
                "status": t.status,
                "package_code": usage.get("package_code"),
                "package_name": usage.get("package_name"),
                "term_value": usage.get("term_value"),
                "term_unit": usage.get("term_unit"),
                "months_assigned": usage.get("months_assigned"),
                "months_used": usage.get("months_used"),
                "months_remaining": usage.get("months_remaining"),
                "years_remaining": usage.get("years_remaining"),
                "days_remaining": usage.get("days_remaining"),
                "renewal_due": usage.get("subscription_ends_at"),
            }
        )
    items.sort(
        key=lambda x: (
            x["days_remaining"] is None,
            x["days_remaining"] if x["days_remaining"] is not None else 10**9,
        )
    )
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "count": len(items),
        "rows": items,
    }


async def build_package_distribution_report(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(m.Tenant))).scalars().all()
    buckets: dict[str, dict[str, Any]] = {}
    for t in rows:
        code = getattr(t, "package_code", None) or "trial"
        b = buckets.setdefault(
            code,
            {
                "package_code": code,
                "package_name": (packages_svc.PACKAGES.get(code) or {}).get("name") or code,
                "tenant_count": 0,
                "active": 0,
                "trial": 0,
                "grace": 0,
                "suspended": 0,
            },
        )
        b["tenant_count"] += 1
        if t.status in b:
            b[t.status] += 1
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "packages": sorted(buckets.values(), key=lambda x: -x["tenant_count"]),
    }


async def build_trial_expirations_report(
    db: AsyncSession, *, within_days: int = 30
) -> dict[str, Any]:
    now = datetime.utcnow()
    rows = (await db.execute(select(m.Tenant))).scalars().all()
    upcoming = []
    for t in rows:
        ends = getattr(t, "subscription_ends_at", None) or t.trial_ends_at or t.grace_ends_at
        if not ends:
            continue
        days = (ends.date() - now.date()).days
        if days > within_days:
            continue
        upcoming.append(
            {
                "tenant_id": t.id,
                "slug": t.slug,
                "company_name": t.company_name,
                "status": t.status,
                "package_code": getattr(t, "package_code", None) or "trial",
                "ends_at": ends,
                "days_remaining": days,
                "kind": (
                    "grace"
                    if t.status == "grace"
                    else ("subscription" if getattr(t, "subscription_ends_at", None) else "trial")
                ),
            }
        )
    upcoming.sort(key=lambda x: x["days_remaining"])
    return {
        "generated_at": now.isoformat() + "Z",
        "within_days": within_days,
        "count": len(upcoming),
        "rows": upcoming,
    }


async def build_all_platform_reports(db: AsyncSession) -> dict[str, Any]:
    return {
        "summary": await build_platform_summary(db),
        "subscriptions": await build_subscription_usage_report(db),
        "packages": await build_package_distribution_report(db),
        "trials": await build_trial_expirations_report(db, within_days=45),
        "tenants": [tenants_svc.serialize_tenant(t) for t in (
            await db.execute(select(m.Tenant).order_by(m.Tenant.company_name.asc()))
        ).scalars().all()],
    }
