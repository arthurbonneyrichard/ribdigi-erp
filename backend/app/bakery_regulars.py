"""Bakery regulars: who orders often, their birthdays, and an opt-in birthday text.

Regulars are found from order phone numbers, so there is no second customer list to keep.
A person is only texted when they have said yes (`texts_ok`), and only once a year.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.bakery import _money, bakery_today
from app.honesty import optional_honest_narrative


def _birthday_in(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError:  # 29 February in a common year
        return date(year, 2, 28)


def next_birthday(today: date, month: int, day: int) -> date:
    this = _birthday_in(today.year, month, day)
    return this if this >= today else _birthday_in(today.year + 1, month, day)


def present(row: m.BakeryRegular, stats: dict | None = None) -> dict:
    stats = stats or {}
    return {
        "phone": row.phone, "name": row.name, "birth_month": row.birth_month, "birth_day": row.birth_day,
        "texts_ok": bool(row.texts_ok), "notes": row.notes,
        "orders": int(stats.get("orders", 0)), "spent": _money(stats.get("spent", 0)),
        "last_order": stats["last_order"].isoformat() if stats.get("last_order") else None,
    }


async def _stats(db: AsyncSession, tenant_id: str) -> dict[str, dict]:
    rows = (await db.execute(
        select(
            m.BakeryOrder.phone, func.max(m.BakeryOrder.customer_name), func.count(m.BakeryOrder.id),
            func.coalesce(func.sum(m.BakeryOrder.total), 0), func.max(m.BakeryOrder.due_date),
        ).where(
            m.BakeryOrder.tenant_id == tenant_id, m.BakeryOrder.phone.is_not(None), m.BakeryOrder.status != "cancelled",
        ).group_by(m.BakeryOrder.phone)
    )).all()
    return {p: {"name": n, "orders": c, "spent": float(t or 0), "last_order": d} for p, n, c, t, d in rows if p}


async def list_regulars(db: AsyncSession, tenant_id: str) -> list[dict]:
    stats = await _stats(db, tenant_id)
    saved = {r.phone: r for r in (await db.execute(select(m.BakeryRegular).where(m.BakeryRegular.tenant_id == tenant_id))).scalars().all()}
    out = []
    for phone in set(stats) | set(saved):
        row = saved.get(phone) or m.BakeryRegular(
            tenant_id=tenant_id, phone=phone, name=stats[phone]["name"], texts_ok=False, birth_month=None, birth_day=None, notes=None
        )
        out.append(present(row, stats.get(phone)))
    out.sort(key=lambda r: (-r["spent"], r["name"] or ""))
    return out


async def save_regular(
    db: AsyncSession, tenant_id: str, *, phone: str, name: str | None, birth_month: int | None, birth_day: int | None,
    texts_ok: bool | None, notes: str | None, clear_birthday: bool,
) -> dict:
    row = (await db.execute(select(m.BakeryRegular).where(m.BakeryRegular.tenant_id == tenant_id, m.BakeryRegular.phone == phone))).scalar_one_or_none()
    known = await _stats(db, tenant_id)
    if row is None:
        if phone not in known:
            raise HTTPException(status_code=404, detail="No order from that phone number yet")
        row = m.BakeryRegular(tenant_id=tenant_id, phone=phone, name=known[phone]["name"], texts_ok=False)
        db.add(row)
    if (birth_month is None) != (birth_day is None):
        raise HTTPException(status_code=422, detail="Give both the birthday month and day")
    if birth_month is not None:
        try:
            date(2024, birth_month, birth_day)
        except ValueError:
            raise HTTPException(status_code=422, detail="That is not a real date") from None
        row.birth_month, row.birth_day = birth_month, birth_day
        row.last_text_year = None
    if clear_birthday:
        row.birth_month = row.birth_day = None
    if name:
        row.name = optional_honest_narrative(name, label="name", max_length=180)
    if texts_ok is not None:
        row.texts_ok = texts_ok
    if notes is not None:
        row.notes = optional_honest_narrative(notes, label="notes", max_length=500)
    await db.flush()
    return present(row, known.get(phone))


async def upcoming_birthdays(db: AsyncSession, tenant_id: str, *, days: int) -> list[dict]:
    today = await bakery_today(db, tenant_id)
    rows = (await db.execute(
        select(m.BakeryRegular).where(m.BakeryRegular.tenant_id == tenant_id, m.BakeryRegular.birth_month.is_not(None))
    )).scalars().all()
    out = []
    for r in rows:
        when = next_birthday(today, r.birth_month, r.birth_day)
        if (when - today).days <= days:
            out.append({**present(r), "on": when.isoformat(), "in_days": (when - today).days})
    out.sort(key=lambda r: r["in_days"])
    return out


async def send_birthday_texts(db: AsyncSession, tenant_id: str) -> dict:
    """Text today's birthdays who said yes, once each year. Best effort: failures are reported."""
    from app import sms

    today = await bakery_today(db, tenant_id)
    company = await db.get(m.Tenant, tenant_id)
    shop = getattr(company, "company_name", "") or "our bakery"
    rows = (await db.execute(
        select(m.BakeryRegular).where(
            m.BakeryRegular.tenant_id == tenant_id, m.BakeryRegular.texts_ok.is_(True),
            m.BakeryRegular.birth_month == today.month, m.BakeryRegular.birth_day == today.day,
        )
    )).scalars().all()
    sent, failed, skipped = 0, [], 0
    for r in rows:
        if r.last_text_year == today.year:
            skipped += 1
            continue
        body = f"Happy birthday {r.name or ''}! From all of us at {shop}. Order your birthday cake with us and make the day sweeter."
        try:
            res = await sms.send_sms(to=r.phone, body=body, tenant=company)
        except Exception:
            failed.append({"phone": r.phone, "reason": "Could not send the text"})
            continue
        if res.sent:
            r.last_text_year = today.year
            sent += 1
        else:
            failed.append({"phone": r.phone, "reason": res.error or ("SMS is not set up" if res.mode == "disabled" else "Not sent")})
    await db.flush()
    return {"sent": sent, "already_texted": skipped, "failed": failed, "birthdays_today": len(rows)}
