"""Server health and performance routes for the software owner console."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app import server_monitor as svc
from app.db import get_db
from app.rbac import is_platform_owner_role
from app.security import require_platform_permission

router = APIRouter(prefix="/platform/monitor", tags=["platform"])

RangeValue = Literal["1h", "6h", "24h", "7d"]
RANGE_SECONDS = {"1h": 3600, "6h": 6 * 3600, "24h": 24 * 3600, "7d": 7 * 24 * 3600}
RANGE_BUCKETS = {"1h": 60, "6h": 72, "24h": 96, "7d": 168}


def env(data=None, message: str = "Operation completed successfully"):
    return {"success": True, "data": data, "message": message}


def _owner_or_admin(claims: dict) -> dict:
    role = claims.get("role") or ""
    if not (is_platform_owner_role(role) or role == "platform_admin"):
        raise HTTPException(status_code=403, detail="Only the software owner or a platform admin can send a test alert")
    return claims


@router.get("")
async def monitor_live(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_platform_permission("platform", "read")),
):
    """One live reading of the server, plus uptime and active alerts."""
    snap = await svc.record(db, source="api")
    day = await svc.load_samples(24 * 3600)
    week = await svc.load_samples(7 * 24 * 3600)
    return env(
        {
            **snap,
            "uptime": {"day": svc.uptime_from(day), "week": svc.uptime_from(week)},
            "active_alerts": await svc.active_alerts(),
            "thresholds": svc.thresholds(),
        }
    )


@router.get("/history")
async def monitor_history(
    range: RangeValue = Query("24h"),  # noqa: A002
    claims: dict = Depends(require_platform_permission("platform", "read")),
):
    seconds = RANGE_SECONDS[range]
    rows = await svc.load_samples(seconds)
    return env(
        {
            "range": range,
            "points": svc.downsample(rows, RANGE_BUCKETS[range], seconds),
            "uptime": svc.uptime_from(rows),
        }
    )


@router.get("/alerts")
async def monitor_alerts(
    limit: int = Query(50, ge=1, le=200),
    claims: dict = Depends(require_platform_permission("platform", "read")),
):
    return env({"events": await svc.recent_events(limit), "active": await svc.active_alerts()})


@router.post("/test-alert")
async def monitor_test_alert(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_platform_permission("platform", "read")),
):
    from app import models as m

    _owner_or_admin(claims)
    user = await db.get(m.User, str(claims.get("sub") or ""))
    by = (getattr(user, "full_name", None) or getattr(user, "email", None) or "A platform admin").strip()
    result = await svc.send_test_alert(db, by=by)
    if not result["delivered"]:
        return env(result, "No platform workspace to notify")
    n = result.get("emailed", 0)
    return env(result, f"Test alert sent: in-app note plus {n} email{'s' if n != 1 else ''} to platform staff")


@router.get("/launch-checks")
async def monitor_launch_checks(
    db: AsyncSession = Depends(get_db),
    claims: dict = Depends(require_platform_permission("platform", "read")),
):
    """Commercial launch checklist: what is ready and how to fix what is not."""
    return env(await svc.launch_checks(db))
