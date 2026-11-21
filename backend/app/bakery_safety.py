"""Bakery food safety: temperature checks and signed daily checklists.

A bakery inspector (Ghana FDA, a customer, an insurer) asks for written proof that fridges were
cold, ovens were hot and the shop was cleaned. Each point has a safe range; a reading outside it
must say what was done about it. Checklists are signed per day. Nothing here touches the books.
"""

from __future__ import annotations

import html
from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.bakery import _bounds, bakery_today
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative

# Typical safe ranges in degrees Celsius; a manager can change them per point.
POINT_KINDS = {
    "fridge": (0.0, 5.0),
    "freezer": (-25.0, -18.0),
    "display": (0.0, 8.0),
    "oven": (160.0, 260.0),
    "proofer": (25.0, 40.0),
    "other": (-30.0, 300.0),
}

CHECKLISTS = {
    "opening": [
        "Hands washed and clean aprons worn",
        "Work surfaces and tables sanitised",
        "Ovens and proofers on and at temperature",
        "Fridge and freezer temperatures recorded",
        "No signs of pests; bins emptied",
        "Today's labels and allergen cards ready",
    ],
    "closing": [
        "Unsold stock sorted: day-old, discount or thrown away",
        "Ovens and gas switched off",
        "Floors swept and mopped",
        "Equipment washed and sanitised",
        "Bins taken out; waste stored away from food",
        "Fridge doors closed and shop locked up",
    ],
    "cleaning": [
        "Mixers and moulds deep cleaned",
        "Ovens and extraction cleaned",
        "Fridge and freezer wiped inside",
        "Drains and sinks cleaned",
        "Cleaning chemicals stored away from food",
    ],
    "delivery": [
        "Delivery vehicle clean",
        "Goods checked against the order",
        "Cold goods arrived cold",
        "Packaging undamaged, dates in order",
        "Rejected goods recorded and returned",
    ],
}


def _round1(v) -> float:
    return round(float(v or 0), 1)


def present_point(p: m.BakerySafetyPoint) -> dict:
    return {
        "id": p.id, "name": p.name, "kind": p.kind, "min_c": money_json(p.min_c), "max_c": money_json(p.max_c),
        "checks_per_day": p.checks_per_day, "is_active": bool(p.is_active),
    }


def present_reading(r: m.BakerySafetyReading, point_name: str | None = None) -> dict:
    return {
        "id": r.id, "point_id": r.point_id, "point_name": point_name, "reading_c": money_json(r.reading_c),
        "in_range": bool(r.in_range), "action_taken": r.action_taken, "recorded_by": r.recorded_by,
        "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
    }


def present_check(c: m.BakerySafetyCheck) -> dict:
    return {
        "id": c.id, "kind": c.kind, "check_date": c.check_date.isoformat(), "items": c.items,
        "all_done": bool(c.all_done), "notes": c.notes, "signed_by": c.signed_by,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


async def list_points(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[m.BakerySafetyPoint]:
    stmt = select(m.BakerySafetyPoint).where(m.BakerySafetyPoint.tenant_id == tenant_id)
    if active_only:
        stmt = stmt.where(m.BakerySafetyPoint.is_active.is_(True))
    return list((await db.execute(stmt.order_by(m.BakerySafetyPoint.name))).scalars().all())


async def create_point(
    db: AsyncSession, tenant_id: str, *, name: str, kind: str, min_c: float | None, max_c: float | None, checks_per_day: int
) -> m.BakerySafetyPoint:
    clean = require_honest_narrative(name, label="name", max_length=100)
    if kind not in POINT_KINDS:
        raise HTTPException(status_code=422, detail="Choose what it is: fridge, freezer, display, oven, proofer or other")
    lo, hi = POINT_KINDS[kind]
    lo = lo if min_c is None else _round1(min_c)
    hi = hi if max_c is None else _round1(max_c)
    if lo >= hi:
        raise HTTPException(status_code=422, detail="The lowest safe temperature must be below the highest")
    dup = (await db.execute(
        select(m.BakerySafetyPoint.id).where(m.BakerySafetyPoint.tenant_id == tenant_id, m.BakerySafetyPoint.name == clean)
    )).first()
    if dup:
        raise HTTPException(status_code=409, detail="A point with that name already exists")
    row = m.BakerySafetyPoint(tenant_id=tenant_id, name=clean, kind=kind, min_c=lo, max_c=hi, checks_per_day=checks_per_day)
    db.add(row)
    await db.flush()
    return row


async def update_point(
    db: AsyncSession, tenant_id: str, point_id: str, *, min_c=None, max_c=None, checks_per_day=None, is_active=None
) -> m.BakerySafetyPoint:
    row = await db.get(m.BakerySafetyPoint, point_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Point not found")
    lo = float(row.min_c) if min_c is None else _round1(min_c)
    hi = float(row.max_c) if max_c is None else _round1(max_c)
    if lo >= hi:
        raise HTTPException(status_code=422, detail="The lowest safe temperature must be below the highest")
    row.min_c, row.max_c = lo, hi
    if checks_per_day is not None:
        row.checks_per_day = checks_per_day
    if is_active is not None:
        row.is_active = is_active
    await db.flush()
    return row


async def record_reading(
    db: AsyncSession, tenant_id: str, *, point_id: str, reading_c: float, action_taken: str | None, user_id: str | None
) -> m.BakerySafetyReading:
    point = await db.get(m.BakerySafetyPoint, point_id)
    if point is None or point.tenant_id != tenant_id or not point.is_active:
        raise HTTPException(status_code=404, detail="Point not found")
    value = _round1(reading_c)
    ok = float(point.min_c) <= value <= float(point.max_c)
    if not ok:
        # A bad reading with no written action is the first thing an inspector looks for.
        action = require_honest_narrative(action_taken, label="what was done about it", max_length=500)
    else:
        action = optional_honest_narrative(action_taken, label="note", max_length=500)
    row = m.BakerySafetyReading(
        tenant_id=tenant_id, point_id=point.id, reading_c=value, in_range=ok, action_taken=action, recorded_by=user_id
    )
    db.add(row)
    await db.flush()
    return row


async def record_check(
    db: AsyncSession, tenant_id: str, *, kind: str, done: list[int], extra_note: str | None, user_id: str | None
) -> m.BakerySafetyCheck:
    if kind not in CHECKLISTS:
        raise HTTPException(status_code=422, detail="Choose a checklist: opening, closing, cleaning or delivery")
    base = CHECKLISTS[kind]
    chosen = set(done)
    if any(i < 0 or i >= len(base) for i in chosen):
        raise HTTPException(status_code=422, detail="That checklist line does not exist")
    items = [{"text": t, "done": i in chosen} for i, t in enumerate(base)]
    row = m.BakerySafetyCheck(
        tenant_id=tenant_id, kind=kind, check_date=await bakery_today(db, tenant_id), items=items,
        all_done=all(i["done"] for i in items),
        notes=optional_honest_narrative(extra_note, label="notes", max_length=500), signed_by=user_id,
    )
    db.add(row)
    await db.flush()
    return row


async def summary(db: AsyncSession, tenant_id: str) -> dict:
    """What a manager checks each morning: readings due, bad readings today, checklists still open."""
    today = await bakery_today(db, tenant_id)
    start, end = await _bounds(db, tenant_id, today, today)
    points = await list_points(db, tenant_id, active_only=True)
    reads = list((await db.execute(
        select(m.BakerySafetyReading).where(
            m.BakerySafetyReading.tenant_id == tenant_id,
            m.BakerySafetyReading.recorded_at >= start,
            m.BakerySafetyReading.recorded_at < end,
        ).order_by(m.BakerySafetyReading.recorded_at.desc())
    )).scalars().all())
    by_point: dict[str, list[m.BakerySafetyReading]] = {}
    for r in reads:
        by_point.setdefault(r.point_id, []).append(r)
    rows = []
    for p in points:
        got = by_point.get(p.id, [])
        last = got[0] if got else None
        rows.append({
            **present_point(p), "taken_today": len(got), "still_due": max(0, p.checks_per_day - len(got)),
            "last_reading": present_reading(last, p.name) if last else None,
            "out_of_range_today": sum(1 for r in got if not r.in_range),
        })
    checks = list((await db.execute(
        select(m.BakerySafetyCheck).where(m.BakerySafetyCheck.tenant_id == tenant_id, m.BakerySafetyCheck.check_date == today)
    )).scalars().all())
    done_kinds = {c.kind for c in checks if c.all_done}
    return {
        "date": today.isoformat(),
        "points": rows,
        "bad_readings_today": sum(r["out_of_range_today"] for r in rows),
        "readings_still_due": sum(r["still_due"] for r in rows),
        "checklists": [
            {"kind": k, "items": CHECKLISTS[k], "done_today": k in done_kinds} for k in ("opening", "closing", "cleaning", "delivery")
        ],
    }


async def history(db: AsyncSession, tenant_id: str, start: date, end: date) -> dict:
    lo, hi = await _bounds(db, tenant_id, start, end)
    names = {p.id: p.name for p in await list_points(db, tenant_id)}
    reads = list((await db.execute(
        select(m.BakerySafetyReading).where(
            m.BakerySafetyReading.tenant_id == tenant_id,
            m.BakerySafetyReading.recorded_at >= lo,
            m.BakerySafetyReading.recorded_at < hi,
        ).order_by(m.BakerySafetyReading.recorded_at)
    )).scalars().all())
    checks = list((await db.execute(
        select(m.BakerySafetyCheck).where(
            m.BakerySafetyCheck.tenant_id == tenant_id,
            m.BakerySafetyCheck.check_date >= start,
            m.BakerySafetyCheck.check_date <= end,
        ).order_by(m.BakerySafetyCheck.check_date, m.BakerySafetyCheck.created_at)
    )).scalars().all())
    return {
        "from": start.isoformat(), "to": end.isoformat(),
        "readings": [present_reading(r, names.get(r.point_id)) for r in reads],
        "checks": [present_check(c) for c in checks],
        "bad_readings": sum(1 for r in reads if not r.in_range),
    }


def render_record(company, data: dict, css: str) -> str:
    h = html.escape
    rows = "".join(
        f"<tr{' class=bad' if not r['in_range'] else ''}><td>{h((r['recorded_at'] or '')[:16].replace('T', ' '))}</td>"
        f"<td>{h(r['point_name'] or '')}</td><td class='r'>{r['reading_c']:.1f}&deg;C</td>"
        f"<td>{'OK' if r['in_range'] else 'OUT OF RANGE'}</td><td>{h(r['action_taken'] or '')}</td></tr>"
        for r in data["readings"]
    ) or "<tr><td colspan='5'>No readings in this period.</td></tr>"
    checks = "".join(
        f"<tr><td>{c['check_date']}</td><td>{h(c['kind'].title())}</td>"
        f"<td>{sum(1 for i in c['items'] if i['done'])}/{len(c['items'])}</td>"
        f"<td>{'Complete' if c['all_done'] else 'INCOMPLETE'}</td><td>{h(c['notes'] or '')}</td></tr>"
        for c in data["checks"]
    ) or "<tr><td colspan='5'>No checklists in this period.</td></tr>"
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>Food safety record</title>"
        f"<style>{css} tr.bad td{{font-weight:bold}}</style></head><body>"
        f"<h2>{h(getattr(company, 'company_name', '') or '')}</h2><h3>Food safety record {data['from']} to {data['to']}</h3>"
        f"<p>{len(data['readings'])} temperature readings, {data['bad_readings']} outside the safe range.</p>"
        "<h4>Temperature log</h4><table><thead><tr><th>When</th><th>Point</th><th class='r'>Reading</th>"
        "<th>Result</th><th>Action taken</th></tr></thead>"
        f"<tbody>{rows}</tbody></table><h4>Checklists</h4>"
        "<table><thead><tr><th>Date</th><th>List</th><th>Done</th><th>Status</th><th>Notes</th></tr></thead>"
        f"<tbody>{checks}</tbody></table><script>window.onload=()=>window.print()</script></body></html>"
    )
