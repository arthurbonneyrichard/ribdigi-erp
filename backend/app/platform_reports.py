"""Cross-tenant platform reports for software-owner staff."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import packages as packages_svc
from app import schema_compat
from app import store_entitlements as store_ent_svc
from app import tenants as tenants_svc

_OPEN_TICKET_STATUSES = ("new", "in_progress", "waiting_for_tenant")

# Platform dashboard activity. Operational modules (pos, sales, inventory, …) are excluded.
PLATFORM_ACTIVITY: tuple[tuple[str, str], ...] = (
    ("tenants", "tenant_created"),
    ("tenants", "industry_changed"),
    ("tenants", "assign_subscription"),
    ("tenants", "update_modules"),
    ("tenants", "admin_password_reset_requested"),
    ("platform_staff", "create"),
    ("platform_staff", "update"),
    ("platform_staff", "delete"),
    ("platform_staff", "grant_dashboard"),
    ("platform_staff", "revoke_dashboard"),
    ("platform_staff", "email_verified"),
    ("billing", "billing_plan_created"),
    ("billing", "billing_plan_updated"),
    ("billing", "billing_plan_deleted"),
)

_SECRET_DETAIL_KEYS = frozenset(
    {
        "password",
        "admin_password",
        "new_password",
        "password_hash",
        "token",
        "reset_token",
        "secret",
        "totp_secret",
    }
)


async def build_platform_summary(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(m.Tenant).order_by(m.Tenant.created_at.desc()))).scalars().all()
    by_status: dict[str, int] = {}
    by_package: dict[str, int] = {}
    for t in rows:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        code = getattr(t, "package_code", None) or "trial"
        by_package[code] = by_package.get(code, 0) + 1
    open_support_tickets = 0
    if await schema_compat.table_column_names(db, "support_tickets"):
        open_support_tickets = int(
            await db.scalar(
                select(func.count())
                .select_from(m.SupportTicket)
                .where(m.SupportTicket.status.in_(_OPEN_TICKET_STATUSES))
            )
            or 0
        )
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "tenant_count": len(rows),
        "by_status": by_status,
        "by_package": by_package,
        "open_support_tickets": open_support_tickets,
    }


async def build_subscription_usage_report(db: AsyncSession) -> dict[str, Any]:
    from app.saas_billing import company_billing_roster

    rows = (await db.execute(select(m.Tenant).order_by(m.Tenant.company_name.asc()))).scalars().all()
    priced = {row["slug"]: row for row in await company_billing_roster(db)}
    items = []
    for t in rows:
        usage = packages_svc.usage_snapshot(t)
        bill = priced.get(t.slug) or {}
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
                "amount": bill.get("amount"),
                "currency": bill.get("currency"),
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


def _safe_details(details: dict | None) -> dict:
    raw = details if isinstance(details, dict) else {}
    return {k: v for k, v in raw.items() if str(k).lower() not in _SECRET_DETAIL_KEYS}


def _activity_summary(module: str, action: str, details: dict) -> str:
    name = details.get("slug") or details.get("email") or details.get("full_name") or ""
    if action == "tenant_created":
        return f"Tenant created{f' ({name})' if name else ''}"
    if action == "industry_changed":
        return f"Industry changed to {details.get('industry') or 'unknown'}"
    if action == "assign_subscription":
        code = details.get("package_code") or "package"
        amount = details.get("amount")
        if amount is not None:
            return f"Package set to {code} at {amount}"
        return f"Package set to {code}"
    if action == "billing_plan_created":
        code = details.get("code") or ""
        return f"Package created{f' ({code})' if code else ''}"
    if action == "billing_plan_updated":
        code = details.get("code") or ""
        return f"Package updated{f' ({code})' if code else ''}"
    if action == "billing_plan_deleted":
        code = details.get("code") or ""
        return f"Package deleted{f' ({code})' if code else ''}"
    if action == "update_modules":
        return "Feature modules updated"
    if action == "admin_password_reset_requested":
        return "Tenant administrator password reset requested"
    if module == "platform_staff" and action == "create":
        return f"Staff account created{f' ({name})' if name else ''}"
    if module == "platform_staff" and action == "update":
        return "Staff account updated"
    if module == "platform_staff" and action == "delete":
        return f"Staff account deleted{f' ({name})' if name else ''}"
    if module == "platform_staff" and action == "grant_dashboard":
        return f"Staff dashboard access granted{f' ({name})' if name else ''}"
    if module == "platform_staff" and action == "revoke_dashboard":
        return f"Staff dashboard access revoked{f' ({name})' if name else ''}"
    if module == "platform_staff" and action == "email_verified":
        return f"Staff account verified{f' ({name})' if name else ''}"
    return f"{module} {action}"


async def build_platform_directory(db: AsyncSession) -> list[dict[str, Any]]:
    """Platform-level tenant summary. No sales, stock, orders, or payments."""
    tenants = (
        await db.execute(select(m.Tenant).order_by(m.Tenant.company_name.asc()))
    ).scalars().all()
    user_counts = dict(
        (
            await db.execute(select(m.User.tenant_id, func.count()).group_by(m.User.tenant_id))
        ).all()
    )
    store_counts = dict(
        (
            await db.execute(select(m.Store.tenant_id, func.count()).group_by(m.Store.tenant_id))
        ).all()
    )
    branch_counts = dict(
        (
            await db.execute(
                select(m.Branch.tenant_id, func.count()).group_by(m.Branch.tenant_id)
            )
        ).all()
    )
    admins = (
        await db.execute(
            select(
                m.User.tenant_id,
                m.User.email,
                m.User.email_verified,
                m.User.created_at,
            )
            .where(m.User.role == "company_admin")
            .order_by(m.User.created_at.asc())
        )
    ).all()
    admin_state: dict[str, list[bool]] = {}
    admin_emails: dict[str, str] = {}
    for tenant_id, email, verified, _created in admins:
        admin_state.setdefault(tenant_id, []).append(bool(verified))
        # Earliest company_admin email is the account used to create the tenant.
        if tenant_id not in admin_emails and email:
            admin_emails[tenant_id] = str(email)

    rows = []
    for tenant in tenants:
        flags = admin_state.get(tenant.id) or []
        if not flags:
            account_status = "no_administrator"
        elif all(flags):
            account_status = "verified"
        else:
            account_status = "pending_verification"
        rows.append(
            {
                "id": tenant.id,
                "company_name": tenant.company_name,
                "slug": tenant.slug,
                "status": tenant.status,
                "industry": tenant.industry,
                "industry_label": tenants_svc.industry_label(getattr(tenant, "industry", None)),
                "store_mode": "multi" if store_ent_svc.is_multi_store(tenant) else "single",
                "user_count": int(user_counts.get(tenant.id) or 0),
                "store_count": int(store_counts.get(tenant.id) or 0),
                "branch_count": int(branch_counts.get(tenant.id) or 0),
                "created_at": tenant.created_at,
                "admin_email": admin_emails.get(tenant.id),
                "account_status": account_status,
                "provisioning_status": account_status,
            }
        )
    return rows


async def build_platform_activity(db: AsyncSession, *, limit: int = 50) -> list[dict[str, Any]]:
    """Cross-tenant platform events only (not store operational audit)."""
    clauses = [
        and_(m.AuditLog.module == module, m.AuditLog.action == action)
        for module, action in PLATFORM_ACTIVITY
    ]
    rows = (
        await db.execute(
            select(m.AuditLog)
            .where(or_(*clauses))
            .order_by(m.AuditLog.created_at.desc())
            .limit(min(max(int(limit or 50), 1), 200))
        )
    ).scalars().all()
    items = []
    for row in rows:
        details = _safe_details(row.details if isinstance(row.details, dict) else {})
        items.append(
            {
                "id": row.id,
                "created_at": row.created_at,
                "tenant_id": row.tenant_id,
                "actor_user_id": row.user_id,
                "module": row.module,
                "action": row.action,
                "entity": row.entity,
                "entity_id": row.entity_id,
                "summary": _activity_summary(row.module, row.action, details),
                "details": details,
            }
        )
    return items
