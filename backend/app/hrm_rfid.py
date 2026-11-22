"""RFID / card attendance.

A reader (a card terminal or a small controller) is registered once and given a token, shown
a single time; only its SHA-256 is kept. The reader POSTs taps to `/hrm/rfid/punch` with that
token. A card number maps to one staff member. Each tap is stored once (reader + reference),
as in or out alternating with the person's last tap, marked source `rfid` for HR to check on
the daily sheet.

This is a framework with simulated-traffic tests only. It has not been run against a real
reader; the reader (or its firmware script) must be set up to send the HTTP request below.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import require_honest_narrative

MAX_AGE = timedelta(hours=72)
MAX_AHEAD = timedelta(minutes=5)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def serialize_reader(r: m.HrmRfidReader) -> dict:
    return {"id": r.id, "name": r.name, "site_id": r.site_id, "active": bool(r.is_active),
            "last_seen_at": r.last_seen_at.isoformat() + "Z" if r.last_seen_at else None}


async def add_reader(db: AsyncSession, tenant_id: str, *, name: str, site_id: str | None, user_id) -> tuple[m.HrmRfidReader, str]:
    from app import hrm

    if site_id:
        site = await db.get(m.HrmSite, site_id)
        if site is None or site.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Site not found")
    token = "rfid_" + secrets.token_urlsafe(32)
    row = m.HrmRfidReader(tenant_id=tenant_id, name=require_honest_narrative(name, label="name", max_length=120), token_hash=_hash(token), site_id=site_id)
    db.add(row)
    await db.flush()
    await hrm._audit(db, tenant_id, user_id, "hrm_rfid_reader_added", "hrm_rfid_reader", row.id, {"name": row.name})
    return row, token


async def switch_off(db: AsyncSession, tenant_id: str, reader_id: str, user_id) -> m.HrmRfidReader:
    from app import hrm

    row = await db.get(m.HrmRfidReader, reader_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Reader not found")
    row.is_active = False
    await hrm._audit(db, tenant_id, user_id, "hrm_rfid_reader_off", "hrm_rfid_reader", row.id, {})
    await db.flush()
    return row


async def readers(db: AsyncSession, tenant_id: str) -> list[m.HrmRfidReader]:
    return list((await db.execute(select(m.HrmRfidReader).where(m.HrmRfidReader.tenant_id == tenant_id).order_by(m.HrmRfidReader.created_at))).scalars())


def _uid(card_uid: str) -> str:
    uid = (card_uid or "").strip().upper().replace(" ", "").replace(":", "")
    if not (4 <= len(uid) <= 40) or not uid.isalnum():
        raise HTTPException(status_code=422, detail="A card number is 4 to 40 letters and digits")
    return uid


async def assign_card(db: AsyncSession, tenant_id: str, employee_id: str, card_uid: str, user_id) -> dict:
    from app import hrm

    emp = await hrm._employee(db, tenant_id, employee_id)
    if emp.status != "active":
        raise HTTPException(status_code=409, detail="This person has left")
    uid = _uid(card_uid)
    taken = (await db.execute(select(m.HrmRfidCard).where(m.HrmRfidCard.tenant_id == tenant_id, m.HrmRfidCard.card_uid == uid))).scalar_one_or_none()
    if taken is not None:
        if taken.employee_id == emp.id and taken.is_active:
            return {"employee_id": emp.id, "card_uid": uid}
        if taken.is_active:
            raise HTTPException(status_code=409, detail="That card is already issued to someone else")
        await db.delete(taken)
        await db.flush()
    # one live card per person: a new card replaces the old one
    for old in (await db.execute(select(m.HrmRfidCard).where(m.HrmRfidCard.employee_id == emp.id, m.HrmRfidCard.is_active.is_(True)))).scalars():
        old.is_active = False
    db.add(m.HrmRfidCard(tenant_id=tenant_id, employee_id=emp.id, card_uid=uid))
    await hrm._audit(db, tenant_id, user_id, "hrm_rfid_card_issued", "hrm_employee", emp.id, {"card_tail": uid[-4:]})
    await db.flush()
    return {"employee_id": emp.id, "card_uid": uid}


async def cards(db: AsyncSession, tenant_id: str) -> list[dict]:
    people = {p.id: p.full_name for p in (await db.execute(select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id))).scalars()}
    rows = (await db.execute(select(m.HrmRfidCard).where(m.HrmRfidCard.tenant_id == tenant_id, m.HrmRfidCard.is_active.is_(True)))).scalars()
    return [{"employee_id": c.employee_id, "name": people.get(c.employee_id), "card_uid": c.card_uid} for c in rows]


async def reader_for_token(db: AsyncSession, token: str | None) -> m.HrmRfidReader:
    if not token or not token.startswith("rfid_"):
        raise HTTPException(status_code=401, detail="Reader token needed")
    row = (await db.execute(select(m.HrmRfidReader).where(m.HrmRfidReader.token_hash == _hash(token)))).scalar_one_or_none()
    if row is None or not hmac.compare_digest(row.token_hash, _hash(token)) or not row.is_active:
        raise HTTPException(status_code=401, detail="Reader token not recognised")
    return row


async def punch(db: AsyncSession, reader: m.HrmRfidReader, *, card_uid: str, ref: str, at: datetime | None) -> dict:
    now = datetime.utcnow()
    when = at or now
    if when > now + MAX_AHEAD or when < now - MAX_AGE:
        raise HTTPException(status_code=422, detail="The tap time is too old or in the future")
    reader.last_seen_at = now
    tenant_id = reader.tenant_id
    ext = f"rfid:{reader.id[:8]}:{ref}"[:80]
    if (await db.execute(select(m.HrmClockEvent.id).where(m.HrmClockEvent.tenant_id == tenant_id, m.HrmClockEvent.external_ref == ext))).first():
        return {"result": "duplicate"}
    uid = _uid(card_uid)
    card = (await db.execute(select(m.HrmRfidCard).where(m.HrmRfidCard.tenant_id == tenant_id, m.HrmRfidCard.card_uid == uid, m.HrmRfidCard.is_active.is_(True)))).scalar_one_or_none()
    if card is None:
        return {"result": "unknown_card"}
    person = await db.get(m.HrmEmployee, card.employee_id)
    if person is None or person.status != "active":
        return {"result": "left"}
    last = (
        await db.execute(
            select(m.HrmClockEvent).where(m.HrmClockEvent.employee_id == person.id, m.HrmClockEvent.voided.is_(False), m.HrmClockEvent.at < when)
            .order_by(m.HrmClockEvent.at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    kind = "out" if last is not None and last.kind == "in" and (when - last.at) < timedelta(hours=20) else "in"
    db.add(m.HrmClockEvent(tenant_id=tenant_id, employee_id=person.id, kind=kind, at=when, source="rfid", site_id=reader.site_id, external_ref=ext))
    await db.flush()
    return {"result": "stored", "kind": kind, "name": person.full_name}
