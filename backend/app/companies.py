"""Company CRUD + subscription limit enforcement (ADR-490)."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import workspace as workspace_svc
from app.rbac import permissions_for_role

# Fallback labels when business_types catalog row is missing (tests / legacy industry codes).
INDUSTRY_LABELS: dict[str, str] = {
    "supermarket": "Supermarket",
    "mini_mart": "Mini Mart",
    "pharmacy": "Pharmacy",
    "restaurant": "Restaurant",
    "wholesale": "Wholesale",
    "distribution": "Distribution",
    "retail": "Retail",
    "bakery": "Bakery",
    "hardware": "Hardware",
    "electronics": "Electronics",
    "fashion": "Fashion",
    "general_trading": "General Trading",
    "other": "Other",
}


def business_type_label_for(co: m.Company, business_type: m.BusinessType | None = None) -> str | None:
    if business_type is not None:
        return (business_type.label or "").strip() or None
    industry = (getattr(co, "industry", None) or "").strip().lower()
    if not industry:
        return None
    return INDUSTRY_LABELS.get(industry) or industry.replace("_", " ").title()


def serialize_company(
    co: m.Company, *, business_type: m.BusinessType | None = None
) -> dict:
    return {
        "id": co.id,
        "tenant_id": co.tenant_id,
        "code": co.code,
        "name": co.name,
        "business_type_id": co.business_type_id,
        "business_type_label": business_type_label_for(co, business_type),
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
        "has_logo": bool(co.logo_url),
        "is_active": co.is_active,
        "is_default": co.is_default,
        "store_limit": int(co.store_limit) if getattr(co, "store_limit", None) is not None else None,
        "created_at": co.created_at.isoformat() if co.created_at else None,
    }


async def get_company(db: AsyncSession, *, tenant_id: str, company_id: str) -> m.Company:
    co = await db.get(m.Company, company_id)
    if not co or co.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Company not found")
    return co


async def serialize_company_async(db: AsyncSession, co: m.Company) -> dict:
    bt = None
    if co.business_type_id:
        bt = await db.get(m.BusinessType, co.business_type_id)
    return serialize_company(co, business_type=bt)


def assert_can_manage_company_branding(claims: dict, company_id: str) -> None:
    """Company branding is not a cashier action — admin-like roles only."""
    if claims.get("company_id") and claims.get("company_id") != company_id:
        # Cross-company mutate blocked even for tenant admins acting in another company workspace.
        if claims.get("workspace_kind") == "company":
            raise HTTPException(status_code=404, detail="Company not found")
    role = (claims.get("membership_role") or claims.get("role") or "").strip().lower()
    if role in {"company_admin", "super_admin", "tenant_owner", "tenant_admin"}:
        return
    if claims.get("tenant_admin"):
        return
    raise HTTPException(
        status_code=403,
        detail="Company branding requires a company or tenant administrator role",
    )



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
    from app import store_entitlements as store_ent_svc

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

    industry = (payload.get("industry") or "retail").strip().lower()
    business_type_id = payload.get("business_type_id")
    if not business_type_id and industry:
        bt = (
            await db.execute(select(m.BusinessType).where(m.BusinessType.code == industry))
        ).scalar_one_or_none()
        if bt:
            business_type_id = bt.id

    # Initial store allocation: honor payload, else 1 if tenant has unallocated capacity.
    requested_limit = payload.get("store_limit", None)
    if requested_limit is not None:
        initial_store_limit = int(requested_limit)
    else:
        ent = await store_ent_svc.get_tenant_store_entitlement(db, tenant)
        if ent["max_stores_unlimited"]:
            initial_store_limit = 1
        else:
            unalloc = int(ent.get("unallocated") or 0)
            initial_store_limit = 1 if unalloc >= 1 else 0

    co = m.Company(
        tenant_id=tenant.id,
        code=code,
        name=name,
        business_type_id=business_type_id,
        industry=industry or "retail",
        legal_name=(payload.get("legal_name") or "").strip() or None,
        registration_number=(payload.get("registration_number") or "").strip() or None,
        tax_registration_number=(payload.get("tax_registration_number") or "").strip() or None,
        phone=(payload.get("phone") or "").strip() or None,
        email=(payload.get("email") or "").strip() or None,
        website=(payload.get("website") or "").strip() or None,
        address=(payload.get("address") or "").strip() or None,
        currency=(payload.get("currency") or tenant.currency or "GHS").strip().upper()[:10],
        timezone=(payload.get("timezone") or tenant.timezone or "Africa/Accra").strip(),
        fiscal_year_start=(
            payload.get("fiscal_year_start") or tenant.fiscal_year_start or "01-01"
        ).strip(),
        document_numbering=getattr(tenant, "document_numbering", None),
        invoice_print_template=getattr(tenant, "invoice_print_template", None) or "a4",
        receipt_print_template=getattr(tenant, "receipt_print_template", None) or "thermal_80",
        document_header=getattr(tenant, "document_header", None),
        document_footer=getattr(tenant, "document_footer", None),
        is_active=True,
        is_default=False,
        store_limit=initial_store_limit,
        updated_at=datetime.utcnow(),
    )
    db.add(co)
    await db.flush()

    # If caller requested an explicit allocation, validate against tenant entitlement.
    if requested_limit is not None:
        await store_ent_svc.set_company_store_limit(
            db, tenant=tenant, company=co, store_limit=initial_store_limit
        )

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


async def update_company(
    db: AsyncSession,
    *,
    company: m.Company,
    payload: dict,
) -> m.Company:
    if "name" in payload and payload["name"] is not None:
        name = str(payload["name"]).strip()
        if len(name) < 2:
            raise HTTPException(status_code=400, detail="Company name is required")
        company.name = name
    if "legal_name" in payload:
        company.legal_name = (str(payload["legal_name"] or "").strip() or None)
    if "phone" in payload:
        company.phone = (str(payload["phone"] or "").strip() or None)
    if "email" in payload:
        company.email = (str(payload["email"] or "").strip() or None)
    if "website" in payload:
        company.website = (str(payload["website"] or "").strip() or None)
    if "address" in payload:
        company.address = (str(payload["address"] or "").strip() or None)
    if "tax_registration_number" in payload:
        company.tax_registration_number = (
            str(payload["tax_registration_number"] or "").strip() or None
        )
    if "registration_number" in payload:
        company.registration_number = (
            str(payload["registration_number"] or "").strip() or None
        )
    if "currency" in payload and payload["currency"] is not None:
        cur = str(payload["currency"]).strip().upper()
        if len(cur) < 3 or len(cur) > 10:
            raise HTTPException(status_code=400, detail="Invalid currency")
        company.currency = cur
    if "timezone" in payload and payload["timezone"] is not None:
        tz = str(payload["timezone"]).strip()
        if not tz:
            raise HTTPException(status_code=400, detail="timezone is required")
        company.timezone = tz
    if "fiscal_year_start" in payload and payload["fiscal_year_start"] is not None:
        fys = str(payload["fiscal_year_start"]).strip()
        if len(fys) != 5 or fys[2] != "-":
            raise HTTPException(status_code=400, detail="fiscal_year_start must be MM-DD")
        company.fiscal_year_start = fys
    if "industry" in payload and payload["industry"] is not None:
        industry = str(payload["industry"]).strip().lower()
        company.industry = industry or company.industry
        bt = (
            await db.execute(select(m.BusinessType).where(m.BusinessType.code == industry))
        ).scalar_one_or_none()
        if bt:
            company.business_type_id = bt.id
    if "business_type_id" in payload:
        bt_id = payload["business_type_id"]
        if bt_id:
            bt = await db.get(m.BusinessType, bt_id)
            if not bt:
                raise HTTPException(status_code=400, detail="Unknown business_type_id")
            company.business_type_id = bt.id
            company.industry = bt.code
        else:
            company.business_type_id = None
    company.updated_at = datetime.utcnow()
    await db.flush()
    return company


async def tenant_dashboard_payload(
    db: AsyncSession, *, tenant: m.Tenant, user: m.User
) -> dict:
    from sqlalchemy import func
    from app import store_entitlements as store_ent_svc

    companies = await count(db, m.Company, tenant.id, active_only=True)
    branches = await count(db, m.Branch, tenant.id, active_only=True)
    stores = await count(db, m.Store, tenant.id, active_only=True)
    warehouses = await count(db, m.Warehouse, tenant.id, active_only=True)
    users = await count(db, m.User, tenant.id, active_only=True)
    company_rows = await list_companies_for_user(
        db, tenant_id=tenant.id, user=user, tenant_admin=True
    )
    store_ent = await store_ent_svc.get_tenant_store_entitlement(db, tenant)
    store_by_company = await store_ent_svc.store_usage_by_company(db, tenant_id=tenant.id)
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
                "max_stores": store_ent["max_stores"],
                "max_stores_unlimited": store_ent["max_stores_unlimited"],
                "max_stores_override": store_ent["max_stores_override"],
                "max_warehouses": int(getattr(tenant, "max_warehouses", 5) or 5),
            },
            "usage": {
                "companies": companies,
                "users": users,
                "branches": branches,
                "stores": stores,
                "warehouses": warehouses,
            },
            "store_entitlement": store_ent,
            "store_allocations": store_by_company,
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


async def get_company(
    db: AsyncSession, *, tenant_id: str, company_id: str
) -> m.Company:
    co = (
        await db.execute(
            select(m.Company).where(
                m.Company.id == company_id, m.Company.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if not co:
        raise HTTPException(status_code=404, detail="Company not found")
    return co


def serialize_membership(row: m.UserCompanyMembership, *, user: m.User | None = None) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "company_id": row.company_id,
        "user_id": row.user_id,
        "role": row.role,
        "is_active": bool(row.is_active),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "user_email": user.email if user else None,
        "user_full_name": user.full_name if user else None,
        "user_role": user.role if user else None,
    }


async def list_company_memberships(
    db: AsyncSession, *, tenant_id: str, company_id: str
) -> list[dict]:
    await get_company(db, tenant_id=tenant_id, company_id=company_id)
    rows = (
        await db.execute(
            select(m.UserCompanyMembership, m.User)
            .join(m.User, m.User.id == m.UserCompanyMembership.user_id)
            .where(
                m.UserCompanyMembership.tenant_id == tenant_id,
                m.UserCompanyMembership.company_id == company_id,
            )
            .order_by(m.User.email)
        )
    ).all()
    return [serialize_membership(mem, user=user) for mem, user in rows]


async def assign_company_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    company_id: str,
    user_id: str,
    role: str = "cashier",
) -> m.UserCompanyMembership:
    await get_company(db, tenant_id=tenant_id, company_id=company_id)
    user = (
        await db.execute(
            select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_norm = (role or "cashier").strip().lower()
    perms = permissions_for_role(role_norm)
    if not perms:
        raise HTTPException(status_code=400, detail=f"Unsupported membership role: {role_norm}")

    existing = (
        await db.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.tenant_id == tenant_id,
                m.UserCompanyMembership.user_id == user_id,
                m.UserCompanyMembership.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.role = role_norm
        existing.permissions = perms
        existing.is_active = True
        await db.flush()
        return existing

    row = m.UserCompanyMembership(
        tenant_id=tenant_id,
        user_id=user_id,
        company_id=company_id,
        role=role_norm,
        permissions=perms,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def revoke_company_membership(
    db: AsyncSession,
    *,
    tenant_id: str,
    company_id: str,
    user_id: str,
) -> m.UserCompanyMembership:
    await get_company(db, tenant_id=tenant_id, company_id=company_id)
    row = (
        await db.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.tenant_id == tenant_id,
                m.UserCompanyMembership.user_id == user_id,
                m.UserCompanyMembership.company_id == company_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Membership not found")
    row.is_active = False
    await db.flush()
    return row
