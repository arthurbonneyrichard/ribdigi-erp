"""ADR-490 — Tenant / Company workspace context and membership helpers."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import permissions_for_role


def company_id_match(column, company_id: str | None):
    """Match active company workspace, including legacy NULL-scoped rows.

    Cross-company stamped rows stay isolated. Unscoped (NULL) rows remain
    visible until backfilled — same pattern as audit company scoping.
    """
    if not company_id:
        return None
    return or_(column == company_id, column.is_(None))


def _default_company_store_limit(tenant: m.Tenant) -> int:
    """First-company allocation uses the effective tenant cap (override-aware).

    Do not treat ``max_stores=0`` as missing — ``or 5`` would silently raise the cap.
    """
    from app import store_entitlements as store_ent_svc

    return int(store_ent_svc.effective_tenant_store_limit(tenant))

# Modules usable in tenant workspace (SaaS account admin — not company ops).
TENANT_WORKSPACE_MODULES = frozenset(
    {
        "tenant",
        "tenant_dashboard",
        "companies",
        "subscription",
        "billing",
        "security",
        "users",  # tenant-level user roster / membership mgmt only when explicitly gated
        "backup",  # full-tenant dump — never from company workspace (ADR-490 phase 14)
    }
)

# Modules that require an active company workspace + membership.
COMPANY_OPERATIONAL_MODULES = frozenset(
    {
        "dashboard",
        "inventory",
        "sales",
        "pos",
        "purchasing",
        "expenses",
        "accounting",
        "credit",
        "reports",
        "stores",
        "warehouse",
        "company",  # company settings (legacy path reused under company context)
        "ai",
        "tax",
        "notifications",
        "activity",
        "audit",
    }
)

TENANT_ADMIN_ROLES = frozenset({"super_admin", "company_admin", "tenant_owner", "tenant_admin"})


def is_tenant_admin_role(role: str | None) -> bool:
    return (role or "") in TENANT_ADMIN_ROLES


async def ensure_default_company(db: AsyncSession, tenant: m.Tenant) -> m.Company:
    """Return the tenant's default company, creating one from tenant profile if needed."""
    existing = (
        await db.execute(
            select(m.Company)
            .where(m.Company.tenant_id == tenant.id, m.Company.is_default.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    any_co = (
        await db.execute(select(m.Company).where(m.Company.tenant_id == tenant.id).limit(1))
    ).scalar_one_or_none()
    if any_co:
        any_co.is_default = True
        return any_co
    co = m.Company(
        tenant_id=tenant.id,
        code="MAIN",
        name=tenant.company_name or tenant.slug,
        industry=tenant.industry or "retail",
        legal_name=tenant.legal_name,
        registration_number=tenant.registration_number,
        tax_registration_number=tenant.tax_registration_number,
        phone=tenant.phone,
        email=tenant.email,
        website=tenant.website,
        address=tenant.address,
        currency=tenant.currency or "GHS",
        timezone=tenant.timezone or "Africa/Accra",
        fiscal_year_start=tenant.fiscal_year_start or "01-01",
        logo_url=tenant.logo_url,
        is_active=True,
        is_default=True,
        store_limit=_default_company_store_limit(tenant),
    )
    db.add(co)
    await db.flush()
    return co


async def ensure_membership_for_user(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    user: m.User,
    company: m.Company | None = None,
) -> m.UserCompanyMembership | None:
    """Ensure operational users have membership on the default company."""
    company = company or await ensure_default_company(db, tenant)
    row = (
        await db.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.tenant_id == tenant.id,
                m.UserCompanyMembership.user_id == user.id,
                m.UserCompanyMembership.company_id == company.id,
            )
        )
    ).scalar_one_or_none()
    if row:
        return row
    # Tenant-admin-only accounts may exist without membership until invited to a company.
    if is_tenant_admin_role(user.role) and user.role in {"tenant_owner", "tenant_admin"}:
        return None
    row = m.UserCompanyMembership(
        tenant_id=tenant.id,
        user_id=user.id,
        company_id=company.id,
        role=user.role or "cashier",
        permissions=user.permissions if isinstance(user.permissions, dict) else None,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def list_user_memberships(
    db: AsyncSession, *, tenant_id: str, user_id: str
) -> list[m.UserCompanyMembership]:
    rows = (
        await db.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.tenant_id == tenant_id,
                m.UserCompanyMembership.user_id == user_id,
                m.UserCompanyMembership.is_active.is_(True),
            )
        )
    ).scalars().all()
    return list(rows)


async def get_membership(
    db: AsyncSession, *, tenant_id: str, user_id: str, company_id: str
) -> m.UserCompanyMembership | None:
    return (
        await db.execute(
            select(m.UserCompanyMembership).where(
                m.UserCompanyMembership.tenant_id == tenant_id,
                m.UserCompanyMembership.user_id == user_id,
                m.UserCompanyMembership.company_id == company_id,
                m.UserCompanyMembership.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def resolve_workspace(
    db: AsyncSession,
    *,
    tenant: m.Tenant,
    user: m.User,
    requested_kind: str | None,
    requested_company_id: str | None,
) -> dict:
    """
    Resolve workspace_kind + company_id for the session.
    Never trusts client company_id without membership verification.
    """
    memberships = await list_user_memberships(db, tenant_id=tenant.id, user_id=user.id)
    # Bootstrap legacy users onto default company when missing memberships.
    if not memberships and not is_tenant_admin_role(user.role):
        co = await ensure_default_company(db, tenant)
        mem = await ensure_membership_for_user(db, tenant=tenant, user=user, company=co)
        if mem:
            memberships = [mem]
    elif not memberships and is_tenant_admin_role(user.role):
        # Legacy company_admin / super_admin keep company membership for ops switching.
        if user.role in {"company_admin", "super_admin"}:
            co = await ensure_default_company(db, tenant)
            mem = await ensure_membership_for_user(db, tenant=tenant, user=user, company=co)
            if mem:
                memberships = [mem]

    kind = (requested_kind or "").strip().lower() or None
    company_id = (requested_company_id or "").strip() or None

    if kind == "company" or company_id:
        if not company_id:
            if len(memberships) == 1:
                company_id = memberships[0].company_id
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "COMPANY_CONTEXT_REQUIRED",
                        "message": "Select a company workspace (X-Company-ID).",
                    },
                )
        mem = next((x for x in memberships if x.company_id == company_id), None)
        if not mem:
            # Verify company belongs to tenant then deny (no existence leak across tenants).
            co = await db.get(m.Company, company_id)
            if not co or co.tenant_id != tenant.id:
                raise HTTPException(status_code=404, detail="Company not found")
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "COMPANY_MEMBERSHIP_REQUIRED",
                    "message": "You are not a member of this company.",
                },
            )
        return {
            "workspace_kind": "company",
            "company_id": company_id,
            "membership_role": mem.role,
            "membership_permissions": mem.permissions,
        }

    # Explicit tenant workspace (UI default for tenant admins).
    if kind == "tenant":
        if not is_tenant_admin_role(user.role):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "TENANT_ADMIN_REQUIRED",
                    "message": "Tenant workspace requires a tenant administrator role.",
                },
            )
        return {
            "workspace_kind": "tenant",
            "company_id": None,
            "membership_role": None,
            "membership_permissions": None,
        }

    # Default (no header): prefer company membership so existing ops clients/tests keep working.
    # Frontend tenant-admin shell must send X-Workspace-Kind: tenant to enter account admin mode.
    if memberships:
        mem = memberships[0]
        return {
            "workspace_kind": "company",
            "company_id": mem.company_id,
            "membership_role": mem.role,
            "membership_permissions": mem.permissions,
        }

    if is_tenant_admin_role(user.role):
        return {
            "workspace_kind": "tenant",
            "company_id": None,
            "membership_role": None,
            "membership_permissions": None,
        }

    raise HTTPException(
        status_code=403,
        detail={
            "code": "NO_WORKSPACE",
            "message": "No company membership and no tenant-admin role.",
        },
    )


def assert_tenant_workspace(claims: dict) -> None:
    """Full-tenant admin actions (e.g. backup dump/restore) require tenant workspace."""
    if claims.get("principal") == "platform":
        return
    kind = claims.get("workspace_kind") or "tenant"
    if kind != "tenant":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_WORKSPACE_REQUIRED",
                "message": (
                    "This action requires the tenant workspace. "
                    "Switch out of company context first."
                ),
            },
        )


def assert_module_workspace(claims: dict, module: str) -> None:
    """Enforce tenant vs company workspace for a module."""
    if claims.get("principal") == "platform":
        return
    kind = claims.get("workspace_kind") or "tenant"
    if module in COMPANY_OPERATIONAL_MODULES:
        if kind != "company" or not claims.get("company_id"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "COMPANY_WORKSPACE_REQUIRED",
                    "message": (
                        "Company operational modules require an active company workspace. "
                        "Switch company context first."
                    ),
                },
            )
    if module in {"tenant_dashboard", "companies", "subscription", "backup"} and kind != "tenant":
        # Allow read of companies list from either context for switcher; create stays tenant-gated in routes.
        if module == "companies":
            return
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TENANT_WORKSPACE_REQUIRED",
                "message": "This action requires the tenant workspace.",
            },
        )


def company_scope_filter(model, claims: dict):
    """Return SQLAlchemy filter clauses for tenant + company isolation."""
    clauses = [model.tenant_id == claims["tenant_id"]]
    company_id = claims.get("company_id")
    if company_id and hasattr(model, "company_id"):
        match = company_id_match(model.company_id, company_id)
        if match is not None:
            clauses.append(match)
    return clauses


def assert_record_company(claims: dict, row) -> None:
    """IDOR guard: row must belong to the active company workspace when set."""
    company_id = claims.get("company_id")
    if not company_id or row is None:
        return
    row_cid = getattr(row, "company_id", None)
    if row_cid and row_cid != company_id:
        raise HTTPException(status_code=404, detail="Not found")


def assert_fk_company(row, company_id: str | None, *, detail: str = "Not found") -> None:
    """Create-path FK guard: related row must match workspace company when both set."""
    if not company_id or row is None:
        return
    row_cid = getattr(row, "company_id", None)
    if row_cid and row_cid != company_id:
        raise HTTPException(status_code=404, detail=detail)


def stamp_company_id(claims: dict) -> str | None:
    """Company id to persist on new operational rows (None outside company workspace)."""
    if (claims.get("workspace_kind") or "") != "company":
        return claims.get("company_id")
    return claims.get("company_id")


async def count_active_companies(db: AsyncSession, tenant_id: str) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(m.Company)
                .where(m.Company.tenant_id == tenant_id, m.Company.is_active.is_(True))
            )
        ).scalar_one()
        or 0
    )


async def assert_can_create_company(db: AsyncSession, tenant: m.Tenant) -> None:
    limit = int(getattr(tenant, "max_companies", None) or 1)
    current = await count_active_companies(db, tenant.id)
    if current >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "COMPANY_LIMIT_REACHED",
                "message": (
                    f"Plan limit reached: maximum {limit} companies. "
                    "Upgrade the tenant subscription to add another company."
                ),
                "max_companies": limit,
                "current_companies": current,
            },
        )


def default_permissions_for_membership_role(role: str) -> dict:
    return permissions_for_role(role)
