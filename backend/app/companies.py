"""Company CRUD + subscription limit enforcement (ADR-490)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import workspace as workspace_svc
from app.rbac import permissions_for_role


def serialize_company(co: m.Company) -> dict:
    return {
        "id": co.id,
        "tenant_id": co.tenant_id,
        "code": co.code,
        "name": co.name,
        "business_type_id": co.business_type_id,
        "industry": co.industry,
        "legal_name": co.legal_name,
        "registration_number": co.registration_number,
        "tax_registration_number": co.tax_registration_number,
        "phone": co.phone,
        "email": co.email,
        "website": co.website,
        "address": co.address,
        "currency": co.currency,
        "timezone": co.timezone,
        "fiscal_year_start": co.fiscal_year_start,
        "logo_url": co.logo_url,
        "is_active": co.is_active,
        "is_default": co.is_default,
        "created_at": co.created_at.isoformat() if co.created_at else None,
    }


async def list_business_types(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(m.BusinessType)
            .where(m.BusinessType.is_active.is_(True))
            .order_by(m.BusinessType.sort_order, m.BusinessType.label)
        )
    ).scalars().all()
    if not rows:
        # SQLite test create_all may lack seed rows — return built-in catalog.
        return [
            {"id": code, "code": code, "label": label, "sort_order": i * 10}
            for i, (code, label) in enumerate(
                [
                    ("supermarket", "Supermarket"),
                    ("mini_mart", "Mini Mart"),
                    ("pharmacy", "Pharmacy"),
                    ("restaurant", "Restaurant"),
                    ("wholesale", "Wholesale"),
                    ("distribution", "Distribution"),
                    ("retail", "Retail"),
                    ("bakery", "Bakery"),
                    ("hardware", "Hardware"),
                    ("electronics", "Electronics"),
                    ("fashion", "Fashion"),
                    ("general_trading", "General Trading"),
                    ("other", "Other"),
                ]
            )
        ]
    return [
        {"id": r.id, "code": r.code, "label": r.label, "sort_order": r.sort_order} for r in rows
    ]


async def list_companies_for_user(
    db: AsyncSession, *, tenant_id: str, user: m.User, tenant_admin: bool
) -> list[m.Company]:
    if tenant_admin:
        return list(
            (
                await db.execute(
                    select(m.Company)
                    .where(m.Company.tenant_id == tenant_id)
                    .order_by(m.Company.name)
                )
            ).scalars().all()
        )
    mems = await workspace_svc.list_user_memberships(db, tenant_id=tenant_id, user_id=user.id)
    ids = [mrow.company_id for mrow in mems]
    if not ids:
        return []
    return list(
        (
            await db.execute(
                select(m.Company)
                .where(m.Company.tenant_id == tenant_id, m.Company.id.in_(ids))
                .order_by(m.Company.name)
            )
        ).scalars().all()
    )


async def create_company(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    actor: m.User,
    payload: dict,
) -> m.Company:
    await workspace_svc.assert_can_create_company(db, tenant)
    code = (payload.get("code") or "CO").strip().upper()[:40]
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Company name is required")
    existing = (
        await db.execute(
            select(m.Company).where(m.Company.tenant_id == tenant.id, m.Company.code == code)
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Company code already exists")

    co = m.Company(
        tenant_id=tenant.id,
        code=code,
        name=name,
        business_type_id=payload.get("business_type_id"),
        industry=payload.get("industry") or "retail",
        legal_name=payload.get("legal_name"),
        registration_number=payload.get("registration_number"),
        tax_registration_number=payload.get("tax_registration_number"),
        phone=payload.get("phone"),
        email=payload.get("email"),
        website=payload.get("website"),
        address=payload.get("address"),
        currency=payload.get("currency") or tenant.currency or "GHS",
        timezone=payload.get("timezone") or tenant.timezone or "Africa/Accra",
        fiscal_year_start=payload.get("fiscal_year_start") or tenant.fiscal_year_start or "01-01",
        is_active=True,
        is_default=False,
        updated_at=datetime.utcnow(),
    )
    db.add(co)
    await db.flush()

    # Creator gets company_admin membership
    db.add(
        m.UserCompanyMembership(
            tenant_id=tenant.id,
            user_id=actor.id,
            company_id=co.id,
            role="company_admin",
            permissions=permissions_for_role("company_admin"),
            is_active=True,
        )
    )
    await db.flush()
    return co


async def tenant_dashboard_payload(
    db: AsyncSession, *, tenant: m.Tenant, user: m.User
) -> dict:
    from sqlalchemy import func

    companies = await count(db, m.Company, tenant.id, active_only=True)
    branches = await count(db, m.Branch, tenant.id, active_only=True)
    stores = await count(db, m.Store, tenant.id, active_only=True)
    warehouses = await count(db, m.Warehouse, tenant.id, active_only=True)
    users = await count(db, m.User, tenant.id, active_only=True)
    company_rows = await list_companies_for_user(
        db, tenant_id=tenant.id, user=user, tenant_admin=True
    )
    return {
        "tenant": {
            "id": tenant.id,
            "slug": tenant.slug,
            "name": tenant.company_name,
            "status": tenant.status,
            "plan_code": tenant.plan_code,
            "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
            "grace_ends_at": tenant.grace_ends_at.isoformat() if tenant.grace_ends_at else None,
        },
        "subscription": {
            "plan_code": tenant.plan_code,
            "status": tenant.status,
            "limits": {
                "max_companies": int(getattr(tenant, "max_companies", 1) or 1),
                "max_users": int(getattr(tenant, "max_users", 25) or 25),
                "max_branches": int(getattr(tenant, "max_branches", 5) or 5),
                "max_stores": int(getattr(tenant, "max_stores", 5) or 5),
                "max_warehouses": int(getattr(tenant, "max_warehouses", 5) or 5),
            },
            "usage": {
                "companies": companies,
                "users": users,
                "branches": branches,
                "stores": stores,
                "warehouses": warehouses,
            },
            "billing_deferred": True,
        },
        "counts": {
            "companies": companies,
            "branches": branches,
            "stores": stores,
            "warehouses": warehouses,
            "users": users,
        },
        "companies": [serialize_company(c) for c in company_rows],
    }


async def count(
    db: AsyncSession, model, tenant_id: str, *, active_only: bool = False
) -> int:
    from sqlalchemy import func

    q = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    if active_only and hasattr(model, "is_active"):
        q = q.where(model.is_active.is_(True))
    return int((await db.execute(q)).scalar_one() or 0)
