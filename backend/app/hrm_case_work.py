"""Case file for disciplinary cases and grievances: investigation notes, evidence files,
suspension records, and appeals.

- All of it is confidential: HR managers and company admins only (area "cases").
- Staff see only their own appeal and its decision, never investigation notes or evidence.
- An appeal can be lodged once, on a closed case, within APPEAL_DAYS of closing. It must be
  decided by someone other than the person who closed the case.
- A suspension record is a dated note on a disciplinary case; it does not change pay or access.
  Payroll and sign-in accounts are handled by HR as usual.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import storage as storage_svc
from app.config import settings
from app.honesty import require_honest_narrative

APPEAL_DAYS = 14
FILE_TYPES = storage_svc.ATTACHMENT_CONTENT_TYPES


def _iso(v):
    return v.isoformat() if v else None


async def _case(db, tenant_id, case_id) -> m.HrmCase:
    row = await db.get(m.HrmCase, case_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


async def _audit(db, tenant_id, user_id, action, case_id, details):
    from app import hrm

    await hrm._audit(db, tenant_id, user_id, action, "hrm_case", case_id, details)


def serialize(e: m.HrmCaseEvent) -> dict:
    return {
        "id": e.id, "case_id": e.case_id, "kind": e.kind, "note": e.note, "outcome": e.outcome,
        "starts_on": _iso(e.starts_on), "ends_on": _iso(e.ends_on), "filename": e.filename,
        "has_file": bool(e.storage_key), "at": _iso(e.created_at),
    }


async def events(db, tenant_id, case_id) -> list[m.HrmCaseEvent]:
    return list((await db.execute(
        select(m.HrmCaseEvent).where(m.HrmCaseEvent.tenant_id == tenant_id, m.HrmCaseEvent.case_id == case_id)
        .order_by(m.HrmCaseEvent.created_at)
    )).scalars())


async def timeline(db, tenant_id, case_id) -> list[dict]:
    await _case(db, tenant_id, case_id)
    return [serialize(e) for e in await events(db, tenant_id, case_id)]


async def add_note(db, tenant_id, case_id, note, user_id) -> dict:
    case = await _case(db, tenant_id, case_id)
    if case.status == "closed":
        raise HTTPException(status_code=409, detail="This case is closed")
    e = m.HrmCaseEvent(
        tenant_id=tenant_id, case_id=case_id, kind="investigation", created_by=user_id,
        note=require_honest_narrative(note, label="note", max_length=8000),
    )
    db.add(e)
    await _audit(db, tenant_id, user_id, "hrm_case_note", case_id, {"kind": "investigation"})
    await db.flush()
    return serialize(e)


async def add_evidence(db, tenant_id, case_id, note, file: UploadFile, user_id) -> dict:
    case = await _case(db, tenant_id, case_id)
    if case.status == "closed" and not await _has(db, tenant_id, case_id, "appeal"):
        raise HTTPException(status_code=409, detail="This case is closed")
    stored = await storage_svc.save_upload(
        tenant_id=tenant_id, category="hrm_cases", upload=file, allowed_types=FILE_TYPES,
        max_bytes=int(settings.MEDIA_MAX_ATTACHMENT_BYTES),
    )
    e = m.HrmCaseEvent(
        tenant_id=tenant_id, case_id=case_id, kind="evidence", created_by=user_id,
        note=require_honest_narrative(note, label="description", max_length=500),
        storage_key=stored.key, filename=stored.original_filename, content_type=stored.content_type,
    )
    db.add(e)
    await _audit(db, tenant_id, user_id, "hrm_case_evidence", case_id, {"file": stored.original_filename})
    await db.flush()
    return serialize(e)


async def evidence_file(db, tenant_id, event_id) -> m.HrmCaseEvent:
    e = await db.get(m.HrmCaseEvent, event_id)
    if e is None or e.tenant_id != tenant_id or not e.storage_key:
        raise HTTPException(status_code=404, detail="File not found")
    return e


async def add_suspension(db, tenant_id, case_id, starts_on: date, ends_on: date | None, note, user_id) -> dict:
    case = await _case(db, tenant_id, case_id)
    if case.kind != "disciplinary":
        raise HTTPException(status_code=422, detail="Only a disciplinary case can record a suspension")
    if case.status == "closed":
        raise HTTPException(status_code=409, detail="This case is closed")
    if ends_on and ends_on < starts_on:
        raise HTTPException(status_code=422, detail="The suspension ends before it starts")
    e = m.HrmCaseEvent(
        tenant_id=tenant_id, case_id=case_id, kind="suspension", starts_on=starts_on, ends_on=ends_on, created_by=user_id,
        note=require_honest_narrative(note, label="reason", max_length=2000),
    )
    db.add(e)
    await _audit(db, tenant_id, user_id, "hrm_case_suspension", case_id, {"starts_on": _iso(starts_on), "ends_on": _iso(ends_on)})
    await db.flush()
    return serialize(e)


async def _has(db, tenant_id, case_id, kind) -> bool:
    return any(e.kind == kind for e in await events(db, tenant_id, case_id))


async def appeal_status(db, tenant_id, case: m.HrmCase) -> dict:
    evs = await events(db, tenant_id, case.id)
    appeal = next((e for e in evs if e.kind == "appeal"), None)
    decision = next((e for e in evs if e.kind == "appeal_decision"), None)
    deadline = (case.closed_at + timedelta(days=APPEAL_DAYS)).date() if case.closed_at else None
    can = case.status == "closed" and appeal is None and deadline is not None and date.today() <= deadline
    return {
        "can_appeal": can, "deadline": _iso(deadline),
        "appeal": {"reason": appeal.note, "at": _iso(appeal.created_at)} if appeal else None,
        "decision": {"outcome": decision.outcome, "note": decision.note, "at": _iso(decision.created_at)} if decision else None,
    }


async def lodge_appeal(db, tenant_id, case_id, reason, user_id, *, employee_id: str | None = None) -> dict:
    case = await _case(db, tenant_id, case_id)
    if employee_id is not None and case.employee_id != employee_id:
        raise HTTPException(status_code=404, detail="Case not found")
    status = await appeal_status(db, tenant_id, case)
    if case.status != "closed":
        raise HTTPException(status_code=409, detail="A case can be appealed once it is closed")
    if status["appeal"]:
        raise HTTPException(status_code=409, detail="This case has already been appealed")
    if not status["can_appeal"]:
        raise HTTPException(status_code=409, detail=f"The {APPEAL_DAYS}-day window to appeal has passed")
    db.add(m.HrmCaseEvent(
        tenant_id=tenant_id, case_id=case_id, kind="appeal", created_by=user_id,
        note=require_honest_narrative(reason, label="reason", max_length=4000),
    ))
    await _audit(db, tenant_id, user_id, "hrm_case_appealed", case_id, {})
    from app import hrm_notify

    await hrm_notify.to_hr(db, tenant_id, "Appeal lodged", f"{case.case_number} has been appealed.", entity_type="hrm_case", entity_id=case.id, skip_user=user_id)
    await db.flush()
    return await appeal_status(db, tenant_id, case)


async def decide_appeal(db, tenant_id, case_id, outcome, note, user_id) -> dict:
    case = await _case(db, tenant_id, case_id)
    st = await appeal_status(db, tenant_id, case)
    if not st["appeal"]:
        raise HTTPException(status_code=409, detail="No appeal has been lodged")
    if st["decision"]:
        raise HTTPException(status_code=409, detail="This appeal has already been decided")
    if outcome not in ("upheld", "rejected"):
        raise HTTPException(status_code=422, detail="Uphold or reject the appeal")
    if user_id and user_id == case.closed_by:
        raise HTTPException(status_code=403, detail="Someone other than the person who closed the case must decide the appeal")
    db.add(m.HrmCaseEvent(
        tenant_id=tenant_id, case_id=case_id, kind="appeal_decision", outcome=outcome, created_by=user_id,
        note=require_honest_narrative(note, label="decision note", max_length=4000),
    ))
    await _audit(db, tenant_id, user_id, "hrm_case_appeal_decided", case_id, {"outcome": outcome})
    from app import hrm_notify

    emp = await db.get(m.HrmEmployee, case.employee_id)
    if emp is not None:
        await hrm_notify.to_person(db, tenant_id, emp, "Appeal decided", f"Your appeal on {case.case_number} has been decided.", entity_type="hrm_case", entity_id=case.id)
    await db.flush()
    return await appeal_status(db, tenant_id, case)
