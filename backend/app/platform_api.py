"""Platform-owner HTTP API (ADR-137). Isolated from tenant ERP modules."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit, health as health_svc, platform as platform_svc
from app.db import get_db
from app.models import Tenant
from app.platform_const import PLATFORM_TENANT_ID
from app.security import require_platform_permission

router = APIRouter(prefix="/api/v1/platform", tags=["platform"])


def env(data: Any = None, message: str = "ok", success: bool = True) -> dict[str, Any]:
    return {"success": success, "data": data, "message": message}


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return request.client.host if request.client else None, request.headers.get("user-agent")


@router.get("/dashboard")
async def platform_dashboard(
    claims: dict = Depends(require_platform_permission("platform_dashboard", "read")),
    db: AsyncSession = Depends(get_db),
):
    data = await platform_svc.platform_dashboard_kpis(db)
    return env(data)


@router.get("/tenants")
async def platform_list_tenants(
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
    q: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = await platform_svc.list_customer_tenants(
        db, q=q, status=status, limit=limit, offset=offset
    )
    return env({"items": items, "total": total, "limit": limit, "offset": offset})


@router.get("/tenants/{tenant_id}")
async def platform_get_tenant(
    tenant_id: str,
    claims: dict = Depends(require_platform_permission("platform_tenants", "read")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    data = await platform_svc.get_customer_tenant(db, tenant_id)
    if not data:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return env(data)


@router.post("/tenants/{tenant_id}/suspend")
async def platform_suspend_tenant(
    tenant_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot suspend the platform tenant")
    row = await db.get(Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if row.status == "suspended":
        return env({"id": row.id, "status": row.status}, message="already suspended")
    prev = row.status
    row.status = "suspended"
    await db.commit()
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="platform.tenant.suspend",
        entity="tenant",
        entity_id=tenant_id,
        details={"previous_status": prev, "target_tenant_id": tenant_id},
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    return env({"id": row.id, "status": row.status}, message="tenant suspended")


@router.post("/tenants/{tenant_id}/activate")
async def platform_activate_tenant(
    tenant_id: str,
    request: Request,
    claims: dict = Depends(require_platform_permission("platform_tenants", "write")),
    db: AsyncSession = Depends(get_db),
):
    if tenant_id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=400, detail="Cannot change platform tenant status here")
    row = await db.get(Tenant, tenant_id)
    if not row or row.id == PLATFORM_TENANT_ID:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if row.status == "active":
        return env({"id": row.id, "status": row.status}, message="already active")
    prev = row.status
    row.status = "active"
    await db.commit()
    ip, ua = _client_meta(request)
    await audit.record_event(
        db,
        tenant_id=claims["tenant_id"],
        user_id=claims.get("sub"),
        action="platform.tenant.activate",
        entity="tenant",
        entity_id=tenant_id,
        details={"previous_status": prev, "target_tenant_id": tenant_id},
        ip_address=ip,
        user_agent=ua,
        module="platform_tenants",
    )
    await db.commit()
    return env({"id": row.id, "status": row.status}, message="tenant activated")


@router.get("/health")
async def platform_health(
    claims: dict = Depends(require_platform_permission("platform_health", "read")),
):
    report, _status = await health_svc.assemble_health(deep=True)
    return env(report)


@router.get("/audit")
async def platform_audit(
    claims: dict = Depends(require_platform_permission("platform_audit", "read")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    # query_logs has no offset; fetch limit+offset then slice for MVP.
    rows = await audit.query_logs(
        db,
        tenant_id=PLATFORM_TENANT_ID,
        limit=min(limit + offset, 1000),
    )
    sliced = rows[offset : offset + limit]
    items = [audit.serialize_audit(r) for r in sliced]
    return env({"items": items, "total": len(rows), "limit": limit, "offset": offset})
