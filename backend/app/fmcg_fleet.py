"""FMCG fleet: vehicle register, compliance expiry, service due, running costs and dispatch assignment.

A vehicle must be active and have no expired insurance, roadworthy or licence document before it can
be put on a dispatch, and it can only be on one open dispatch at a time. Fuel, service, repair, tyre
and accident records keep the odometer moving forward only. Costs paid by the company post
Dr 6000 / Cr the payment account; fuel and tolls paid from a van's takings are already booked by
the van expense and are only copied into the vehicle's history, never booked twice.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import fmcg_orders as orders
from app import models as m
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

KINDS = ("van", "truck", "pickup", "motorbike", "other")
STATUSES = ("active", "workshop", "retired")
LOG_KINDS = ("fuel", "service", "repair", "tyre", "accident", "other")
DOCS = (("insurance", "insurance_expiry"), ("roadworthy", "roadworthy_expiry"), ("licence", "licence_expiry"))
WARN_DAYS = 30
PLATE_RE = re.compile(r"^[A-Z0-9][A-Z0-9 -]{1,19}$")


def _km(value) -> float:
    return money_json(round(float(value or 0), 1))


async def _audit(db, tenant_id, user_id, action, entity_id, details) -> None:
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="fmcg", action=action,
        entity="fmcg_vehicle", entity_id=entity_id, details=details,
    )


async def _vehicle(db, tenant_id: str, vehicle_id: str, *, lock: bool = False) -> m.FmcgVehicle:
    stmt = select(m.FmcgVehicle).where(m.FmcgVehicle.id == vehicle_id, m.FmcgVehicle.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return row


async def _driver(db, tenant_id: str, user_id: str | None) -> m.User | None:
    if not user_id:
        return None
    user = (await db.execute(select(m.User).where(m.User.id == user_id, m.User.tenant_id == tenant_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return user


def compliance(v: m.FmcgVehicle, today: date | None = None) -> dict:
    today = today or date.today()
    docs = {}
    expired, expiring, missing = [], [], []
    for label, field in DOCS:
        d = getattr(v, field)
        if d is None:
            state, days = "not_recorded", None
            missing.append(label)
        else:
            days = (d - today).days
            state = "expired" if days < 0 else "expiring" if days <= WARN_DAYS else "ok"
            if state == "expired":
                expired.append(label)
            elif state == "expiring":
                expiring.append(label)
        docs[label] = {"expiry": d.isoformat() if d else None, "days_left": days, "state": state}
    return {"documents": docs, "expired": expired, "expiring": expiring, "not_recorded": missing, "roadworthy": not expired}


def service_state(v: m.FmcgVehicle) -> dict:
    if v.service_every_km is None:
        return {"due": False, "km_to_service": None}
    since = float(v.odometer_km or 0) - float(v.last_service_km or 0)
    left = float(v.service_every_km) - since
    return {"due": left <= 0, "km_to_service": _km(left)}


async def _present(db, v: m.FmcgVehicle) -> dict:
    driver = await db.get(m.User, v.driver_user_id) if v.driver_user_id else None
    busy = (
        await db.execute(
            select(m.FmcgDispatch.dispatch_number).where(
                m.FmcgDispatch.tenant_id == v.tenant_id, m.FmcgDispatch.vehicle_id == v.id, m.FmcgDispatch.status == "open"
            )
        )
    ).scalar_one_or_none()
    return {
        "id": v.id, "plate": v.plate, "name": v.name, "kind": v.kind, "make_model": v.make_model, "status": v.status,
        "driver_user_id": v.driver_user_id, "driver": driver.full_name if driver else None,
        "odometer_km": _km(v.odometer_km), "service_every_km": _km(v.service_every_km) if v.service_every_km is not None else None,
        "last_service_km": _km(v.last_service_km) if v.last_service_km is not None else None,
        "compliance": compliance(v), "service": service_state(v), "on_dispatch": busy,
    }


def _clean_plate(plate: str) -> str:
    clean = re.sub(r"\s+", " ", (plate or "").strip().upper())
    if not PLATE_RE.match(clean):
        raise HTTPException(status_code=422, detail="Enter the number plate, letters, numbers, spaces or dashes")
    return clean


async def create_vehicle(
    db, *, tenant_id: str, plate: str, name: str, kind: str, make_model: str | None, driver_user_id: str | None,
    odometer_km: float, insurance_expiry, roadworthy_expiry, licence_expiry, service_every_km: float | None,
    last_service_km: float | None, user_id,
) -> dict:
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(KINDS)}")
    clean = _clean_plate(plate)
    if (
        await db.execute(select(m.FmcgVehicle.id).where(m.FmcgVehicle.tenant_id == tenant_id, m.FmcgVehicle.plate == clean))
    ).first():
        raise HTTPException(status_code=409, detail="A vehicle with that plate already exists")
    await _driver(db, tenant_id, driver_user_id)
    row = m.FmcgVehicle(
        tenant_id=tenant_id, plate=clean, name=require_honest_narrative(name, label="name", max_length=120), kind=kind,
        make_model=optional_honest_narrative(make_model, label="make and model", max_length=120),
        driver_user_id=driver_user_id, odometer_km=odometer_km, insurance_expiry=insurance_expiry,
        roadworthy_expiry=roadworthy_expiry, licence_expiry=licence_expiry, service_every_km=service_every_km,
        last_service_km=last_service_km if last_service_km is not None else (odometer_km if service_every_km else None),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_vehicle_added", row.id, {"plate": clean})
    return await _present(db, row)


async def update_vehicle(db, *, tenant_id: str, vehicle_id: str, changes: dict, user_id) -> dict:
    row = await _vehicle(db, tenant_id, vehicle_id, lock=True)
    if "status" in changes:
        if changes["status"] not in STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(STATUSES)}")
        if changes["status"] != "active":
            busy = (
                await db.execute(
                    select(m.FmcgDispatch.id).where(
                        m.FmcgDispatch.tenant_id == tenant_id, m.FmcgDispatch.vehicle_id == row.id, m.FmcgDispatch.status == "open"
                    )
                )
            ).first()
            if busy:
                raise HTTPException(status_code=409, detail="This vehicle is on an open dispatch. Settle it first")
        row.status = changes["status"]
    if "driver_user_id" in changes:
        await _driver(db, tenant_id, changes["driver_user_id"])
        row.driver_user_id = changes["driver_user_id"]
    if "name" in changes:
        row.name = require_honest_narrative(changes["name"], label="name", max_length=120)
    for field in ("insurance_expiry", "roadworthy_expiry", "licence_expiry", "service_every_km"):
        if field in changes:
            setattr(row, field, changes[field])
    await _audit(db, tenant_id, user_id, "fmcg_vehicle_updated", row.id, {k: str(v) for k, v in changes.items()})
    await db.flush()
    return await _present(db, row)


async def list_vehicles(db, *, tenant_id: str, status: str | None = None) -> list[dict]:
    stmt = select(m.FmcgVehicle).where(m.FmcgVehicle.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(m.FmcgVehicle.status == status)
    rows = (await db.execute(stmt.order_by(m.FmcgVehicle.plate))).scalars().all()
    return [await _present(db, v) for v in rows]


async def attention(db, *, tenant_id: str) -> list[dict]:
    """Things a fleet manager has to act on: expired or expiring documents and services due."""
    out = []
    for v in (
        await db.execute(
            select(m.FmcgVehicle).where(m.FmcgVehicle.tenant_id == tenant_id, m.FmcgVehicle.status != "retired")
        )
    ).scalars().all():
        c = compliance(v)
        for label in c["expired"]:
            out.append({"vehicle_id": v.id, "plate": v.plate, "level": "expired", "text": f"{v.plate}: {label} has expired"})
        for label in c["expiring"]:
            days = c["documents"][label]["days_left"]
            out.append({"vehicle_id": v.id, "plate": v.plate, "level": "expiring", "text": f"{v.plate}: {label} expires in {days} days"})
        if service_state(v)["due"]:
            out.append({"vehicle_id": v.id, "plate": v.plate, "level": "service", "text": f"{v.plate}: service is due"})
    return out


# ---------------------------------------------------------------- logs

async def add_log(
    db, *, tenant_id: str, vehicle_id: str, kind: str, log_date: date | None, odometer_km: float | None,
    litres: float | None, amount: float, vendor: str | None, note: str | None, pay_method: str | None, user_id,
) -> dict:
    if kind not in LOG_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of: {', '.join(LOG_KINDS)}")
    v = await _vehicle(db, tenant_id, vehicle_id, lock=True)
    when = log_date or date.today()
    if when > date.today():
        raise HTTPException(status_code=422, detail="The date cannot be in the future")
    paid = orders._money(amount)
    if kind == "fuel" and (not litres or litres <= 0 or paid <= 0):
        raise HTTPException(status_code=422, detail="A fuel record needs litres and the amount paid")
    if kind != "fuel" and litres:
        raise HTTPException(status_code=422, detail="Litres only belong on a fuel record")
    text = optional_honest_narrative(note, label="note", max_length=500)
    if kind == "accident" and not text:
        raise HTTPException(status_code=422, detail="Describe what happened")
    if odometer_km is not None:
        if odometer_km + 0.05 < float(v.odometer_km or 0):
            raise HTTPException(
                status_code=409,
                detail={"code": "ODOMETER_BACKWARDS", "message": f"The odometer was already {_km(v.odometer_km):g} km"},
            )
        v.odometer_km = odometer_km
    if kind == "service":
        v.last_service_km = v.odometer_km
    entry_id = None
    if paid > 0:
        if not pay_method:
            raise HTTPException(status_code=422, detail="Say how it was paid")
        method = orders._method(pay_method)
        entry_id = await orders._post(
            db, tenant_id, user_id=user_id, description=f"Vehicle {kind} {v.plate}",
            lines=[
                {"account_code": "6000", "debit": paid, "credit": 0, "description": f"Vehicle {kind}"},
                {"account_code": orders._money_account(method), "debit": 0, "credit": paid, "description": f"Paid by {method}"},
            ],
            reference=v.plate, source="fmcg_vehicle_cost", source_id=v.id,
        )
    row = m.FmcgVehicleLog(
        tenant_id=tenant_id, vehicle_id=v.id, kind=kind, log_date=when, odometer_km=odometer_km, litres=litres,
        amount=paid, vendor=optional_honest_narrative(vendor, label="vendor", max_length=120), note=text,
        journal_entry_id=entry_id, created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "fmcg_vehicle_log", v.id, {"kind": kind, "amount": paid, "odometer_km": odometer_km})
    return _log_row(row)


def _log_row(r: m.FmcgVehicleLog) -> dict:
    return {
        "id": r.id, "vehicle_id": r.vehicle_id, "kind": r.kind, "date": r.log_date.isoformat(),
        "odometer_km": _km(r.odometer_km) if r.odometer_km is not None else None,
        "litres": money_json(r.litres) if r.litres is not None else None, "amount": money_json(r.amount),
        "vendor": r.vendor, "note": r.note, "dispatch_id": r.dispatch_id,
    }


async def list_logs(db, *, tenant_id: str, vehicle_id: str) -> list[dict]:
    await _vehicle(db, tenant_id, vehicle_id)
    rows = (
        await db.execute(
            select(m.FmcgVehicleLog)
            .where(m.FmcgVehicleLog.tenant_id == tenant_id, m.FmcgVehicleLog.vehicle_id == vehicle_id)
            .order_by(m.FmcgVehicleLog.log_date.desc(), m.FmcgVehicleLog.created_at.desc())
            .limit(200)
        )
    ).scalars().all()
    return [_log_row(r) for r in rows]


# ---------------------------------------------------------------- dispatch

async def assign_to_dispatch(db, *, tenant_id: str, dispatch_id: str, vehicle_id: str, user_id) -> dict:
    dispatch = await orders._dispatch(db, tenant_id, dispatch_id, lock=True)
    if dispatch.status != "open":
        raise HTTPException(status_code=409, detail="This dispatch is closed")
    v = await _vehicle(db, tenant_id, vehicle_id, lock=True)
    if v.status != "active":
        raise HTTPException(status_code=409, detail={"code": "VEHICLE_NOT_ACTIVE", "message": f"{v.plate} is {v.status}"})
    c = compliance(v)
    if c["expired"]:
        raise HTTPException(
            status_code=409,
            detail={"code": "VEHICLE_NOT_ROADWORTHY", "message": f"{v.plate} cannot go out: {', '.join(c['expired'])} expired"},
        )
    other = (
        await db.execute(
            select(m.FmcgDispatch.dispatch_number).where(
                m.FmcgDispatch.tenant_id == tenant_id, m.FmcgDispatch.vehicle_id == v.id,
                m.FmcgDispatch.status == "open", m.FmcgDispatch.id != dispatch.id,
            )
        )
    ).scalar_one_or_none()
    if other:
        raise HTTPException(status_code=409, detail={"code": "VEHICLE_BUSY", "message": f"{v.plate} is already on {other}"})
    driver = await db.get(m.User, v.driver_user_id) if v.driver_user_id else None
    dispatch.vehicle_id = v.id
    dispatch.vehicle = v.plate
    if driver:
        dispatch.driver_name = driver.full_name
    await _audit(db, tenant_id, user_id, "fmcg_vehicle_assigned", v.id, {"dispatch_id": dispatch.id})
    await db.flush()
    return {
        "dispatch_id": dispatch.id, "dispatch_number": dispatch.dispatch_number, "vehicle_id": v.id, "plate": v.plate,
        "driver_name": dispatch.driver_name, "service_due": service_state(v)["due"], "documents_expiring": c["expiring"],
    }


# ---------------------------------------------------------------- report

async def cost_report(db, *, tenant_id: str, start: date, end: date) -> list[dict]:
    vehicles = (
        await db.execute(select(m.FmcgVehicle).where(m.FmcgVehicle.tenant_id == tenant_id).order_by(m.FmcgVehicle.plate))
    ).scalars().all()
    out = []
    for v in vehicles:
        logs = (
            await db.execute(
                select(m.FmcgVehicleLog)
                .where(
                    m.FmcgVehicleLog.tenant_id == tenant_id, m.FmcgVehicleLog.vehicle_id == v.id,
                    m.FmcgVehicleLog.log_date >= start, m.FmcgVehicleLog.log_date <= end,
                )
                .order_by(m.FmcgVehicleLog.log_date, m.FmcgVehicleLog.created_at)
            )
        ).scalars().all()
        by_kind = {k: 0.0 for k in LOG_KINDS}
        for r in logs:
            by_kind[r.kind] += float(r.amount or 0)
        odo = [float(r.odometer_km) for r in logs if r.odometer_km is not None]
        km = round(max(odo) - min(odo), 1) if len(odo) >= 2 else None
        fuel = [r for r in logs if r.kind == "fuel" and r.odometer_km is not None and r.litres]
        efficiency = None
        if len(fuel) >= 2:
            driven = float(fuel[-1].odometer_km) - float(fuel[0].odometer_km)
            used = sum(float(r.litres) for r in fuel[1:])
            efficiency = round(driven / used, 2) if used > 0 and driven > 0 else None
        total = sum(by_kind.values())
        trips = (
            await db.execute(
                select(func.count()).select_from(m.FmcgDispatch).where(
                    m.FmcgDispatch.tenant_id == tenant_id, m.FmcgDispatch.vehicle_id == v.id,
                    m.FmcgDispatch.dispatch_date >= start, m.FmcgDispatch.dispatch_date <= end,
                )
            )
        ).scalar_one()
        sales = (
            await db.execute(
                select(func.coalesce(func.sum(m.FmcgOrder.total), 0))
                .join(m.FmcgDispatch, m.FmcgDispatch.id == m.FmcgOrder.dispatch_id)
                .where(
                    m.FmcgOrder.tenant_id == tenant_id, m.FmcgDispatch.vehicle_id == v.id, m.FmcgOrder.status == "delivered",
                    m.FmcgDispatch.dispatch_date >= start, m.FmcgDispatch.dispatch_date <= end,
                )
            )
        ).scalar_one()
        out.append(
            {
                "vehicle_id": v.id, "plate": v.plate, "name": v.name, "trips": int(trips), "sales_delivered": money_json(sales),
                "fuel_litres": round(sum(float(r.litres or 0) for r in logs if r.kind == "fuel"), 2),
                **{f"{k}_cost": money_json(round(by_kind[k], 2)) for k in LOG_KINDS},
                "total_cost": money_json(round(total, 2)), "km_driven": km,
                "cost_per_km": round(total / km, 2) if km else None, "km_per_litre": efficiency,
                "cost_pct_of_sales": round(100 * total / float(sales), 1) if float(sales or 0) > 0 else None,
            }
        )
    return out
