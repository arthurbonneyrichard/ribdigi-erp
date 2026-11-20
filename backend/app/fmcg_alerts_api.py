"""FMCG alert routes: run the scan now and see what has been sent. Managers and admins only."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_alerts as svc
from app import fmcg_orders as orders
from app.db import get_db
from app.security import require_permission

router = APIRouter(prefix="/fmcg/alerts", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


@router.post("/scan")
async def scan_now(claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "alerts")
    data = await svc.scan(db, claims["tenant_id"])
    await db.commit()
    return _env(data, "Scan finished")


@router.get("/log")
async def alert_log(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "alerts")
    return _env(await svc.log(db, tenant_id=claims["tenant_id"]))
