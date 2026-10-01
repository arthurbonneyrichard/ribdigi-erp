"""Customer create/list/update. Ownership comes from auth, never from the browser."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import customer_groups as customer_groups_svc
from app import models as m
from app import schema_compat
from app.models import uid

COMPANY_REQUIRED = "Company is required. Create a company for this workspace, then try again."
GROUP_UNAVAILABLE = "Customer group was not found or is not available in this company."
GROUP_INACTIVE = "Customer group is inactive. Choose an active group or leave it empty."
TENANT_UNAVAILABLE = "Workspace is missing or not available."
STORE_UNAVAILABLE = "Store was not found or is not available."


def field_error(field: str, message: str, *, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}],
    )


def map_party_integrity_error(exc: IntegrityError) -> HTTPException:
    raw = str(getattr(exc, "orig", None) or exc).lower()
    if "customer_group" in raw:
        return field_error("customer_group", GROUP_UNAVAILABLE)
    if "company_id" in raw or "companies" in raw:
        return field_error("company", COMPANY_REQUIRED)
    if "tenant_id" in raw or "tenants." in raw:
        return HTTPException(status_code=400, detail=TENANT_UNAVAILABLE)
    if "store_id" in raw or "stores." in raw:
        return field_error("store", STORE_UNAVAILABLE)
    return HTTPException(
        status_code=400,
        detail=(
            "Could not save the customer. Check that company and customer group "
            "exist for this workspace."
        ),
    )


async def live_column_nullable(db: AsyncSession, table_name: str, column: str) -> bool | None:
    def _probe(sync_session) -> bool | None:
        conn = sync_session.connection()
        insp = sa_inspect(conn)
        if not insp.has_table(table_name):
            return None
        for col in insp.get_columns(table_name):
            if col["name"] == column:
                return bool(col.get("nullable", True))
        return None

    return await db.run_sync(_probe)


async def ownership_from_auth(db: AsyncSession, claims: dict) -> tuple[str, str | None, set[str]]:
    """Tenant + company from the authenticated session. Ignore client-supplied IDs."""
    tenant_id = (claims or {}).get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")
    party_cols = await schema_compat.table_column_names(db, "parties")
    company_id = await schema_compat.resolve_tenant_company_id(db, str(tenant_id))
    return str(tenant_id), company_id, party_cols


async def require_party_company_id(
    db: AsyncSession, *, tenant_id: str, party_cols: set[str], company_id: str | None
) -> str | None:
    if "company_id" not in party_cols:
        return None
    if company_id:
        return company_id
    nullable = await live_column_nullable(db, "parties", "company_id")
    if nullable is False:
        raise field_error("company", COMPANY_REQUIRED)
    return None


async def resolve_assignable_group(
    db: AsyncSession,
    *,
    tenant_id: str,
    group_id: str | None,
    company_id: str | None,
) -> m.CustomerGroup | None:
    if not group_id:
        return None
    try:
        row = await customer_groups_svc.require_active_group(db, tenant_id, group_id)
    except HTTPException as exc:
        detail = str(exc.detail or "")
        if exc.status_code == 400 and "inactive" in detail.lower():
            raise field_error("customer_group", GROUP_INACTIVE) from exc
        raise field_error("customer_group", GROUP_UNAVAILABLE, status_code=404) from exc
    group_cols = await schema_compat.table_column_names(db, "customer_groups")
    if company_id and "company_id" in group_cols:
        live = await schema_compat.fetch_live_dicts(
            db, "customer_groups", "id = :id AND tenant_id = :tid", {"id": row.id, "tid": tenant_id}
        )
        gid = live[0].get("company_id") if live else getattr(row, "company_id", None)
        if gid and str(gid) != str(company_id):
            raise field_error("customer_group", GROUP_UNAVAILABLE, status_code=404)
    return row


def apply_company_where(stmt, table: str, cols: set[str], company_id: str | None):
    if not company_id or "company_id" not in cols:
        return stmt
    return stmt.where(
        text(f"{table}.company_id = :_party_company_id").bindparams(_party_company_id=company_id)
    )


async def list_customers(
    db: AsyncSession,
    claims: dict,
    *,
    status: str | None = None,
) -> list[m.Party]:
    tenant_id, company_id, party_cols = await ownership_from_auth(db, claims)
    await customer_groups_svc.ensure_default_groups(db, tenant_id)
    stmt = select(m.Party).where(m.Party.tenant_id == tenant_id, m.Party.kind == "customer")
    if status:
        stmt = stmt.where(m.Party.status == status)
    stmt = apply_company_where(stmt, "parties", party_cols, company_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_customer(db: AsyncSession, claims: dict, customer_id: str) -> m.Party:
    tenant_id, company_id, party_cols = await ownership_from_auth(db, claims)
    stmt = select(m.Party).where(
        m.Party.id == customer_id,
        m.Party.tenant_id == tenant_id,
        m.Party.kind == "customer",
    )
    stmt = apply_company_where(stmt, "parties", party_cols, company_id)
    party = (await db.execute(stmt)).scalar_one_or_none()
    if not party:
        raise HTTPException(status_code=404, detail="Customer not found")
    return party


async def create_customer(
    db: AsyncSession,
    claims: dict,
    data: dict,
) -> tuple[m.Party, m.CustomerGroup | None]:
    tenant_id, company_id, party_cols = await ownership_from_auth(db, claims)
    company_id = await require_party_company_id(
        db, tenant_id=tenant_id, party_cols=party_cols, company_id=company_id
    )
    data = dict(data)
    data.pop("tenant_id", None)
    data.pop("company_id", None)
    group_id = data.pop("customer_group_id", None) or None
    group = await resolve_assignable_group(
        db, tenant_id=tenant_id, group_id=group_id, company_id=company_id
    )
    values = {
        **data,
        "id": uid(),
        "tenant_id": tenant_id,
        "kind": "customer",
        "customer_group_id": group.id if group else None,
    }
    if company_id:
        values["company_id"] = company_id
    try:
        await schema_compat.insert_matching_row(db, "parties", values)
        await db.flush()
        party = await schema_compat.get_mapped(db, m.Party, values["id"])
        if party is None:
            await db.rollback()
            raise HTTPException(status_code=500, detail="The server could not complete this request.")
    except IntegrityError as exc:
        await db.rollback()
        raise map_party_integrity_error(exc) from exc
    if company_id:
        try:
            object.__setattr__(party, "company_id", company_id)
        except Exception:
            pass
    return party, group


async def load_group(
    db: AsyncSession, tenant_id: str, group_id: str | None
) -> m.CustomerGroup | None:
    if not group_id:
        return None
    return await customer_groups_svc.get_group(db, tenant_id, group_id)
