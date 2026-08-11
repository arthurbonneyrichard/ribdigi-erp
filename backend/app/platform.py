"""Platform Owner services — Ribdigi House SaaS console (ADR-137)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import tenants as tenants_svc
from app.platform_const import (
    PLATFORM_COMPANY_NAME,
    PLATFORM_TENANT_ID,
    PLATFORM_TENANT_SLUG,
)


async def record_platform_email_delivery(
    db: AsyncSession,
    *,
    actor_user_id: str | None,
    purpose: str,
    recipient: str,
    related_action: str,
    email_result: Any,
    extra: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Stage 90 E1 — append-only delivery outcome for House-initiated emails."""
    details = {
        "purpose": purpose,
        "recipient": recipient,
        "related_action": related_action,
        "sent": bool(getattr(email_result, "sent", False)),
        "mode": getattr(email_result, "mode", None),
        "error": getattr(email_result, "error", None),
        "fabricated_success": False,
    }
    if extra:
        details.update(extra)
    await audit_svc.record_event(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        user_id=actor_user_id,
        action="platform.email.delivery",
        entity="email",
        entity_id=None,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent,
        module="platform_email",
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
    at_risk = await list_at_risk_tenants(db, within_days=14)
    return {
        "total_tenants": total,
        "active_tenants": by_status.get("active", 0),
        "trial_tenants": by_status.get("trial", 0),
        "grace_tenants": by_status.get("grace", 0),
        "suspended_tenants": by_status.get("suspended", 0),
        "at_risk_count": int(at_risk.get("total") or 0),
        "at_risk_within_days": int(at_risk.get("within_days") or 14),
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


async def platform_tenant_growth(db: AsyncSession, *, months: int = 12) -> dict:
    """Tenants created by calendar month (customer tenants only).

    Aggregates in Python so SQLite tests and PostgreSQL prod share one path
    (avoids Postgres-only ``date_trunc``).
    """
    await ensure_platform_tenant(db)
    months = max(1, min(int(months or 12), 36))
    now = datetime.utcnow()
    # Inclusive window: first day of (months-1) months ago through now.
    year = now.year
    month = now.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    window_start = datetime(year, month, 1)
    created_ats = (
        await db.execute(
            select(m.Tenant.created_at).where(
                _customer_tenant_filter(), m.Tenant.created_at >= window_start
            )
        )
    ).scalars().all()
    by_month: dict[str, int] = {}
    for created_at in created_ats:
        if created_at is None:
            continue
        key = created_at.strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0) + 1
    series: list[dict] = []
    y, mo = year, month
    for _ in range(months):
        key = f"{y:04d}-{mo:02d}"
        series.append({"month": key, "tenants": by_month.get(key, 0)})
        mo += 1
        if mo > 12:
            mo = 1
            y += 1
    return {"series": series, "months": months}


async def platform_tenant_status_chart(db: AsyncSession) -> dict:
    kpis = await platform_dashboard_kpis(db)
    breakdown = kpis.get("status_breakdown") or {}
    slices = [
        {"status": status, "count": int(count)}
        for status, count in sorted(breakdown.items(), key=lambda x: (-x[1], x[0]))
    ]
    return {"slices": slices, "total": int(kpis.get("total_tenants") or 0)}


async def platform_plan_distribution(db: AsyncSession) -> dict:
    await ensure_platform_tenant(db)
    rows = (
        await db.execute(
            select(m.Tenant.plan_code, func.count())
            .where(_customer_tenant_filter())
            .group_by(m.Tenant.plan_code)
            .order_by(func.count().desc())
        )
    ).all()
    slices = [
        {"plan_code": str(plan or "unset"), "count": int(count)} for plan, count in rows
    ]
    return {"slices": slices, "total": sum(s["count"] for s in slices)}


async def provision_customer_tenant(
    db: AsyncSession,
    *,
    slug: str,
    company_name: str,
    industry: str = "retail",
    currency: str = "GHS",
    timezone: str = "Africa/Accra",
    tax_jurisdiction: str = "GH",
    admin_email: str,
    admin_password: str,
    admin_full_name: str = "Company Administrator",
    plan_code: str = "trial",
) -> tuple[m.Tenant, m.User, str]:
    """Provision a customer tenant with admin + defaults (Stage 86 P1).

    Returns ``(tenant, admin_user, email_verification_raw_token)``.
    Lazy-imports seed helpers to avoid circular imports with ``app.api``.
    """
    from app.api import seed_tenant_defaults
    from app.rbac import permissions_for_role
    from app.security import hash_password, issue_one_time_token, validate_password_strength

    validate_password_strength(admin_password)
    assert_not_reserved_tenant_slug(slug)
    slug_clean = (slug or "").strip().lower()
    existing = (
        await db.execute(select(m.Tenant).where(m.Tenant.slug == slug_clean))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Tenant slug exists")

    plan = (plan_code or "trial").strip().lower()
    if plan not in tenants_svc.VALID_PLAN_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"plan_code must be one of: {sorted(tenants_svc.VALID_PLAN_CODES)}",
        )

    tenant = m.Tenant(
        slug=slug_clean,
        company_name=company_name.strip(),
        industry=(industry or "retail").strip() or "retail",
        currency=(currency or "GHS").strip() or "GHS",
        timezone=(timezone or "Africa/Accra").strip() or "Africa/Accra",
        tax_jurisdiction=(tax_jurisdiction or "GH").strip().upper() or "GH",
        status="trial",
        plan_code=plan,
        trial_ends_at=tenants_svc.default_trial_ends_at(),
        trial_notices={},
    )
    db.add(tenant)
    await db.flush()

    admin_name = (admin_full_name or "Company Administrator").strip() or "Company Administrator"
    admin = m.User(
        tenant_id=tenant.id,
        email=str(admin_email).strip().lower(),
        full_name=admin_name,
        password_hash=hash_password(admin_password),
        role="company_admin",
        email_verified=False,
        permissions=permissions_for_role("company_admin"),
    )
    db.add(admin)
    await db.flush()
    await seed_tenant_defaults(db, tenant.id)

    raw, token_hash, expires = issue_one_time_token()
    db.add(
        m.AuthToken(
            tenant_id=tenant.id,
            user_id=admin.id,
            purpose="email_verify",
            token_hash=token_hash,
            expires_at=expires,
        )
    )
    await db.flush()
    return tenant, admin, raw


async def platform_subscriptions_roster(db: AsyncSession) -> dict:
    """Customer tenant × plan_code roster (Stage 85 R1) — metadata only, no MRR/checkout.

    Honesty: this is not paid billing Complete (ADR-002). ``subscriptions_live_claimed``
    and fabricated MRR remain false.
    """
    await ensure_platform_tenant(db)
    rows = (
        await db.execute(
            select(m.Tenant)
            .where(_customer_tenant_filter())
            .order_by(m.Tenant.company_name.asc())
        )
    ).scalars().all()
    items = []
    for t in rows:
        items.append(
            {
                "tenant_id": t.id,
                "slug": t.slug,
                "company_name": t.company_name,
                "status": t.status,
                "plan_code": getattr(t, "plan_code", None) or "trial",
                "trial_ends_at": t.trial_ends_at.isoformat() + "Z" if t.trial_ends_at else None,
                "billing": "deferred",
            }
        )
    distribution = await platform_plan_distribution(db)
    return {
        "deferred_billing": True,
        "mrr": None,
        "checkout_enabled": False,
        "subscriptions_live": False,
        "message": (
            "Tenant×plan roster is commercial metadata only. Subscription billing, "
            "checkout, and fabricated MRR remain deferred (ADR-002)."
        ),
        "plan_codes": sorted(tenants_svc.VALID_PLAN_CODES),
        "distribution": distribution,
        "items": items,
        "total": len(items),
    }


async def platform_industry_distribution(db: AsyncSession) -> dict:
    await ensure_platform_tenant(db)
    rows = (
        await db.execute(
            select(m.Tenant.industry, func.count())
            .where(_customer_tenant_filter())
            .group_by(m.Tenant.industry)
            .order_by(func.count().desc())
        )
    ).all()
    slices = [
        {"industry": str(ind or "unset"), "count": int(count)} for ind, count in rows
    ]
    return {"slices": slices, "total": sum(s["count"] for s in slices)}


async def platform_user_growth(db: AsyncSession, *, months: int = 12) -> dict:
    """Customer-tenant users created by calendar month (dialect-portable)."""
    await ensure_platform_tenant(db)
    months = max(1, min(int(months or 12), 36))
    now = datetime.utcnow()
    year = now.year
    month = now.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    window_start = datetime(year, month, 1)
    created_ats = (
        await db.execute(
            select(m.User.created_at)
            .join(m.Tenant, m.Tenant.id == m.User.tenant_id)
            .where(m.Tenant.id != PLATFORM_TENANT_ID, m.User.created_at >= window_start)
        )
    ).scalars().all()
    by_month: dict[str, int] = {}
    for created_at in created_ats:
        if created_at is None:
            continue
        key = created_at.strftime("%Y-%m")
        by_month[key] = by_month.get(key, 0) + 1
    series: list[dict] = []
    y, mo = year, month
    for _ in range(months):
        key = f"{y:04d}-{mo:02d}"
        series.append({"month": key, "users": by_month.get(key, 0)})
        mo += 1
        if mo > 12:
            mo = 1
            y += 1
    return {"series": series, "months": months}


async def get_customer_tenant_admin(db: AsyncSession, tenant_id: str) -> m.User | None:
    """Primary Tenant Admin (`company_admin`) for House assist (Stage 89 A1)."""
    return (
        await db.execute(
            select(m.User)
            .where(
                m.User.tenant_id == tenant_id,
                m.User.role == "company_admin",
                m.User.is_active == True,  # noqa: E712
            )
            .order_by(m.User.created_at.asc())
            .limit(1)
        )
    ).scalar_one_or_none()


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
    admin = await get_customer_tenant_admin(db, t.id)
    base = tenants_svc.serialize_tenant(t)
    base.update(
        {
            "user_count": user_count,
            "store_count": store_count,
            "branch_count": branch_count,
            "last_activity_at": last_activity.isoformat() + "Z" if last_activity else None,
            "platform_notes": getattr(t, "platform_notes", None),
            "tenant_admin": (
                {
                    "id": admin.id,
                    "email": admin.email,
                    "full_name": admin.full_name,
                    "email_verified": bool(admin.email_verified),
                    "role": admin.role,
                }
                if admin
                else None
            ),
        }
    )
    return base


async def list_customer_tenants(
    db: AsyncSession,
    *,
    q: str | None = None,
    status: str | None = None,
    plan_code: str | None = None,
    industry: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    await ensure_platform_tenant(db)
    filters = [_customer_tenant_filter()]
    if status:
        filters.append(m.Tenant.status == status)
    if plan_code and plan_code.strip():
        filters.append(m.Tenant.plan_code == plan_code.strip().lower())
    if industry and industry.strip():
        filters.append(func.lower(m.Tenant.industry) == industry.strip().lower())
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        admin_tenant_ids = (
            select(m.User.tenant_id)
            .where(
                m.User.role == "company_admin",
                m.User.is_active == True,  # noqa: E712
                func.lower(m.User.email).like(like),
            )
            .distinct()
        )
        filters.append(
            or_(
                func.lower(m.Tenant.slug).like(like),
                func.lower(m.Tenant.company_name).like(like),
                m.Tenant.id == q.strip(),
                m.Tenant.id.in_(admin_tenant_ids),
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


async def last_house_email_delivery(db: AsyncSession, tenant_id: str) -> dict | None:
    """Stage 91 N1 — latest platform.email.delivery for a customer tenant."""
    rows = await audit_svc.query_logs(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        module="platform_email",
        action="platform.email.delivery",
        limit=200,
    )
    for row in rows:
        details = row.details if isinstance(row.details, dict) else {}
        if details.get("target_tenant_id") == tenant_id:
            return {
                "created_at": row.created_at.isoformat() + "Z" if row.created_at else None,
                "purpose": details.get("purpose"),
                "recipient": details.get("recipient"),
                "related_action": details.get("related_action"),
                "sent": details.get("sent"),
                "mode": details.get("mode"),
                "error": details.get("error"),
                "fabricated_success": bool(details.get("fabricated_success"))
                if details.get("fabricated_success") is not None
                else False,
            }
    return None


async def get_customer_tenant(db: AsyncSession, tenant_ref: str) -> dict | None:
    try:
        tenant = await tenants_svc.resolve_tenant(db, tenant_ref)
    except HTTPException:
        return None
    if tenant.id == PLATFORM_TENANT_ID:
        return None
    row = await _enrich_tenant_row(db, tenant)
    row["last_house_email_delivery"] = await last_house_email_delivery(db, tenant.id)
    return row


async def list_at_risk_tenants(db: AsyncSession, *, within_days: int = 14) -> dict:
    """Trial/grace tenants nearing (or past) expiry — Stage 88 R1 ops queue."""
    await ensure_platform_tenant(db)
    within_days = max(1, min(int(within_days or 14), 90))
    now = datetime.utcnow()
    cutoff = now + timedelta(days=within_days)
    rows = (
        await db.execute(
            select(m.Tenant)
            .where(
                _customer_tenant_filter(),
                or_(
                    (m.Tenant.status == "trial")
                    & (m.Tenant.trial_ends_at.is_not(None))
                    & (m.Tenant.trial_ends_at <= cutoff),
                    (m.Tenant.status == "grace")
                    & (m.Tenant.grace_ends_at.is_not(None))
                    & (m.Tenant.grace_ends_at <= cutoff),
                ),
            )
            .order_by(m.Tenant.trial_ends_at.asc().nulls_last(), m.Tenant.grace_ends_at.asc().nulls_last())
        )
    ).scalars().all()
    items = []
    for t in rows:
        row = await _enrich_tenant_row(db, t)
        ends = t.grace_ends_at if t.status == "grace" else t.trial_ends_at
        items.append(
            {
                **{k: row.get(k) for k in (
                    "id",
                    "slug",
                    "company_name",
                    "status",
                    "plan_code",
                    "trial_ends_at",
                    "grace_ends_at",
                    "days_remaining",
                    "platform_notes",
                )},
                "risk_ends_at": ends.isoformat() + "Z" if ends else None,
                "within_days": within_days,
            }
        )
    return {"within_days": within_days, "items": items, "total": len(items)}


def customer_tenants_to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "slug",
            "company_name",
            "status",
            "plan_code",
            "industry",
            "trial_ends_at",
            "grace_ends_at",
            "days_remaining",
            "user_count",
            "store_count",
            "last_activity_at",
            "suspended_reason",
            "created_at",
        ]
    )
    for r in rows:
        def _fmt(v):
            if v is None:
                return ""
            if hasattr(v, "isoformat"):
                return v.isoformat()
            return str(v)

        writer.writerow(
            [
                r.get("id") or "",
                r.get("slug") or "",
                r.get("company_name") or "",
                r.get("status") or "",
                r.get("plan_code") or "",
                r.get("industry") or "",
                _fmt(r.get("trial_ends_at")),
                _fmt(r.get("grace_ends_at")),
                "" if r.get("days_remaining") is None else r.get("days_remaining"),
                r.get("user_count") if r.get("user_count") is not None else "",
                r.get("store_count") if r.get("store_count") is not None else "",
                _fmt(r.get("last_activity_at")),
                r.get("suspended_reason") or "",
                _fmt(r.get("created_at")),
            ]
        )
    return buf.getvalue()


def customer_tenants_to_pdf(rows: list[dict]) -> bytes:
    from app.report_export import to_pdf as build_pdf

    lines = [
        f"{r.get('slug') or '-'} | {r.get('company_name') or '-'} | "
        f"{r.get('status') or '-'} | plan={r.get('plan_code') or '-'} | "
        f"days={r.get('days_remaining') if r.get('days_remaining') is not None else '-'}"
        for r in rows
    ]
    if not lines:
        lines = ["No customer tenants in selection."]
    return build_pdf("Customer tenants", lines, subtitle=f"{len(rows)} tenant(s)")
