"""FMCG alerts: batch expiry bands and vehicle document expiry, sent once per band.

Batches use the company's own warning days (90, 60, 30, 14, 7 by default). A batch is alerted when it
first falls inside a band and again when it falls inside the next, tighter band, and once more when it
has expired, never twice for the same band (``fmcg_alert_log``), even if the first alert was read or
deleted. Vehicle insurance, roadworthy and licence documents use 30, 14 and 7 days, then expired.

Each alert is an in-app notification for the right staff plus an email and, where a person has switched
SMS on for that category in their notification settings and has a phone number, an SMS. Those channels
and each person's choices are the existing notification settings; this module only decides what is
worth saying and to whom.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_batches as batches_svc
from app import fmcg_fleet as fleet_svc
from app import models as m
from app import notifications as notifications_svc
from app.packages import canonicalize_industry

VEHICLE_BANDS = (30, 14, 7)
BATCH_ROLES = ["company_admin", "super_admin", "fmcg_manager", "fmcg_storekeeper", "fmcg_quality"]
FLEET_ROLES = ["company_admin", "super_admin", "fmcg_manager", "fmcg_fleet"]


def band_for(days: int | None, bands: list[int] | tuple[int, ...]) -> int | None:
    """The tightest warning band a count of days left falls in; 0 means already expired; None means none yet."""
    if days is None:
        return None
    if days < 0:
        return 0
    inside = [b for b in bands if days <= b]
    return min(inside) if inside else None


async def _already(db, tenant_id: str, kind: str, ref: str, band: int) -> bool:
    return (
        await db.execute(
            select(m.FmcgAlertLog.id).where(
                m.FmcgAlertLog.tenant_id == tenant_id, m.FmcgAlertLog.kind == kind, m.FmcgAlertLog.ref_id == ref, m.FmcgAlertLog.band == band
            )
        )
    ).first() is not None


async def scan(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or canonicalize_industry(getattr(tenant, "industry", None)) != "fmcg":
        return {"batch": 0, "vehicle": 0, "skipped": "not an FMCG company"}
    sent = {"batch": 0, "vehicle": 0}

    policy = await batches_svc.get_policy(db, tenant_id)
    view = await batches_svc.list_batches(db, tenant_id=tenant_id)
    for b in view["batches"]:
        band = band_for(b["days_to_expiry"], policy["warn_days"])
        if band is None or await _already(db, tenant_id, "batch", b["id"], band):
            continue
        expired = band == 0
        when = f"expired {abs(b['days_to_expiry'])} days ago" if expired else f"expires in {b['days_to_expiry']} days ({b['expiry_date']})"
        await notifications_svc.create_notification(
            db, tenant_id=tenant_id, category="batch_expiry",
            title="Batch expired" if expired else f"Batch expiring within {band} days",
            message=f"{b['product_name']} batch {b['batch_number']}: {b['quantity']:g} units {when}. Stock value at cost {b['value_at_cost']:,.2f}.",
            entity_type="product_batch", entity_id=b["id"], roles=BATCH_ROLES,
        )
        db.add(m.FmcgAlertLog(tenant_id=tenant_id, kind="batch", ref_id=b["id"], band=band, summary=f"{b['product_name']} {b['batch_number']}"))
        sent["batch"] += 1

    today = date.today()
    for v in (await db.execute(select(m.FmcgVehicle).where(m.FmcgVehicle.tenant_id == tenant_id, m.FmcgVehicle.status != "retired"))).scalars().all():
        for label, field in fleet_svc.DOCS:
            expiry = getattr(v, field)
            if expiry is None:
                continue
            days = (expiry - today).days
            band = band_for(days, VEHICLE_BANDS)
            ref = f"{v.id}:{label}"
            if band is None or await _already(db, tenant_id, "vehicle", ref, band):
                continue
            await notifications_svc.create_notification(
                db, tenant_id=tenant_id, category="fleet_document",
                title=f"{v.plate}: {label} expired" if band == 0 else f"{v.plate}: {label} expiring within {band} days",
                message=(f"The {label} for {v.plate} expired on {expiry.isoformat()}. The vehicle cannot go on a dispatch until it is renewed."
                         if band == 0 else f"The {label} for {v.plate} expires on {expiry.isoformat()} ({days} days)."),
                entity_type="fmcg_vehicle", entity_id=v.id, roles=FLEET_ROLES,
            )
            db.add(m.FmcgAlertLog(tenant_id=tenant_id, kind="vehicle", ref_id=ref, band=band, summary=f"{v.plate} {label}"))
            sent["vehicle"] += 1
    await db.flush()
    return sent


async def log(db: AsyncSession, *, tenant_id: str, limit: int = 100) -> list[dict]:
    rows = (
        await db.execute(
            select(m.FmcgAlertLog).where(m.FmcgAlertLog.tenant_id == tenant_id).order_by(m.FmcgAlertLog.sent_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [{"id": r.id, "kind": r.kind, "band": r.band, "summary": r.summary, "sent_at": r.sent_at.isoformat(timespec="seconds")} for r in rows]
