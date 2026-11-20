"""FMCG command centre and reporting centre routes. Managers and admins only."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_dashboard as dash
from app import fmcg_exports as exports
from app import fmcg_orders as orders
from app import fmcg_reports as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


@router.get("/dashboard")
async def command_centre(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "dashboard")
    return _env(await dash.command_centre(db, tenant_id=claims["tenant_id"]))


@router.get("/reports/centre")
async def report_catalogue(claims=Depends(require_permission("fmcg", "read"))):
    orders.job(claims, "reports")
    return _env(svc.CATALOGUE)


@router.get("/reports/run")
async def report_run(
    report: str,
    start: date | None = None,
    end: date | None = None,
    format: Literal["json", "csv", "xlsx", "pdf"] = "json",
    product_id: UuidIdValue | None = None,
    category_id: UuidIdValue | None = None,
    brand_id: UuidIdValue | None = None,
    outlet_id: UuidIdValue | None = None,
    route_id: UuidIdValue | None = None,
    territory_id: UuidIdValue | None = None,
    supplier_id: UuidIdValue | None = None,
    vehicle_id: UuidIdValue | None = None,
    rep: Annotated[str | None, Query(min_length=1, max_length=150)] = None,
    status: Annotated[str | None, Query(min_length=1, max_length=20)] = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "reports")
    filters = {
        "product_id": product_id, "category_id": category_id, "brand_id": brand_id, "outlet_id": outlet_id, "route_id": route_id,
        "territory_id": territory_id, "supplier_id": supplier_id, "vehicle_id": vehicle_id, "rep": rep, "status": status,
    }
    data = await svc.run(db, tenant_id=claims["tenant_id"], report_id=report, start=start, end=end, filters=filters)
    stamp = f"fmcg-{report}-{date.today().isoformat()}"
    if format == "csv":
        return Response(
            content="﻿" + svc.to_csv(data), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{stamp}.csv"'},
        )
    if format == "xlsx":
        return Response(
            content=exports.to_xlsx(data), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{stamp}.xlsx"'},
        )
    if format == "pdf":
        return Response(
            content=exports.to_pdf(data), media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{stamp}.pdf"'},
        )
    return _env(data)
