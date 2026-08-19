"""CSV export for platform plans catalog, subscriptions roster & house settings (Stage 150).

Honesty: metadata-only — no fabricated MRR, no live checkout, ADR-002 remains deferred.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import platform as platform_svc
from app import tenants as tenants_svc
from app.platform_const import PLATFORM_TENANT_ID
from app.session_passkey_doc_export import _cell

PLAN_EXPORT_COLUMNS = [
    "row_type",
    "deferred_billing",
    "mrr",
    "checkout_enabled",
    "subscriptions_live",
    "code",
    "label",
    "blurb",
    "soft_limit_stores",
    "soft_limit_users",
    "tenant_count",
    "distribution_total",
]

SUBSCRIPTION_EXPORT_COLUMNS = [
    "deferred_billing",
    "mrr",
    "checkout_enabled",
    "subscriptions_live",
    "billing",
    "tenant_id",
    "slug",
    "company_name",
    "status",
    "plan_code",
    "industry",
    "admin_email",
    "user_count",
    "store_count",
    "trial_ends_at",
    "grace_ends_at",
    "created_at",
]

SETTINGS_EXPORT_COLUMNS = [
    "tenant_id",
    "slug",
    "company_name",
    "inactivity_timeout_minutes",
    "support_email",
    "support_phone",
    "timezone",
    "date_format",
    "time_format",
    "number_format",
    "status",
    "plan_code",
]

INDUSTRY_EXPORT_COLUMNS = [
    "row_type",
    "code",
    "label",
    "catalog_total",
]


async def export_platform_plans_csv(db: AsyncSession) -> str:
    """Stage 150 P1 — plan catalog + distribution CSV (metadata honesty)."""
    distribution = await platform_svc.platform_plan_distribution(db)
    catalog = tenants_svc.plan_catalog_items()
    slices = {
        s.get("plan_code"): s.get("count")
        for s in (distribution.get("slices") or [])
        if isinstance(s, dict)
    }
    total = distribution.get("total")
    honesty = {
        "deferred_billing": "true",
        "mrr": "",
        "checkout_enabled": "false",
        "subscriptions_live": "false",
    }

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PLAN_EXPORT_COLUMNS)
    writer.writeheader()

    summary = {k: "" for k in PLAN_EXPORT_COLUMNS}
    summary.update(
        {
            **honesty,
            "row_type": "summary",
            "distribution_total": _cell(total),
        }
    )
    writer.writerow(summary)

    for item in catalog:
        limits = item.get("soft_limits") or {}
        code = item.get("code")
        row = {k: "" for k in PLAN_EXPORT_COLUMNS}
        row.update(
            {
                **honesty,
                "row_type": "catalog",
                "code": _cell(code),
                "label": _cell(item.get("label")),
                "blurb": _cell(item.get("blurb")),
                "soft_limit_stores": _cell(limits.get("stores")),
                "soft_limit_users": _cell(limits.get("users")),
                "tenant_count": _cell(slices.get(code, 0)),
                "distribution_total": _cell(total),
            }
        )
        writer.writerow(row)
    return buf.getvalue()


async def export_platform_subscriptions_csv(db: AsyncSession) -> str:
    """Stage 150 R1 — tenant×plan subscriptions roster CSV (metadata only; no MRR)."""
    roster = await platform_svc.platform_subscriptions_roster(db)
    honesty = {
        "deferred_billing": "true",
        "mrr": "",
        "checkout_enabled": "false",
        "subscriptions_live": "false",
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SUBSCRIPTION_EXPORT_COLUMNS)
    writer.writeheader()
    for item in roster.get("items") or []:
        writer.writerow(
            {
                **honesty,
                "billing": _cell(item.get("billing") or "deferred"),
                "tenant_id": _cell(item.get("tenant_id")),
                "slug": _cell(item.get("slug")),
                "company_name": _cell(item.get("company_name")),
                "status": _cell(item.get("status")),
                "plan_code": _cell(item.get("plan_code")),
                "industry": _cell(item.get("industry")),
                "admin_email": _cell(item.get("admin_email")),
                "user_count": _cell(item.get("user_count")),
                "store_count": _cell(item.get("store_count")),
                "trial_ends_at": _cell(item.get("trial_ends_at")),
                "grace_ends_at": _cell(item.get("grace_ends_at")),
                "created_at": _cell(item.get("created_at")),
            }
        )
    return buf.getvalue()


async def export_platform_settings_csv(db: AsyncSession) -> str:
    """Stage 150 S1 — Ribdigi House settings CSV (secret-free)."""
    await platform_svc.ensure_platform_tenant(db)
    tenant = await db.get(m.Tenant, PLATFORM_TENANT_ID)
    if tenant is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Platform tenant not found")
    payload = {
        "tenant_id": tenant.id,
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "inactivity_timeout_minutes": int(
            getattr(tenant, "inactivity_timeout_minutes", None) or 30
        ),
        "support_email": getattr(tenant, "email", None),
        "support_phone": getattr(tenant, "phone", None),
        "timezone": getattr(tenant, "timezone", None) or "Africa/Accra",
        "date_format": getattr(tenant, "date_format", None) or "DD/MM/YYYY",
        "time_format": getattr(tenant, "time_format", None) or "24h",
        "number_format": getattr(tenant, "number_format", None) or "1,234.56",
        "status": tenant.status,
        "plan_code": getattr(tenant, "plan_code", None) or "enterprise",
    }
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow({k: _cell(payload.get(k)) for k in SETTINGS_EXPORT_COLUMNS})
    return buf.getvalue()


async def export_platform_industries_csv(db: AsyncSession) -> str:
    """Stage 152 I1 — industry catalog CSV (House provisioning / filter codes)."""
    await platform_svc.ensure_platform_tenant(db)
    catalog = tenants_svc.industry_catalog_items()
    total = len(catalog)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=INDUSTRY_EXPORT_COLUMNS)
    writer.writeheader()
    writer.writerow(
        {
            "row_type": "summary",
            "code": "",
            "label": "",
            "catalog_total": _cell(total),
        }
    )
    for item in catalog:
        writer.writerow(
            {
                "row_type": "catalog",
                "code": _cell(item.get("code")),
                "label": _cell(item.get("label")),
                "catalog_total": _cell(total),
            }
        )
    return buf.getvalue()
