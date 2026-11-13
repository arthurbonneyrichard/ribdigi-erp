"""Documents on a staff file, and company policies staff must read.

- HR uploads a file to one person's record (contract, ID copy, certificate, letter) or to the
  whole company (a policy or handbook). Files go to the tenant's media store, never inline.
- "Needs acknowledgement": the person (or, for a company policy, every active member of staff
  with a sign-in) opens it and confirms by typing their full name as it is on their staff record.
  The typed name, time and sign-in are kept. This is a record that they read and accepted it,
  not a qualified electronic signature.
- "Confidential" files (a medical note, a disciplinary letter) are for HR managers only and are
  not shown to the person or to HR officers.
- A file is never edited; HR archives it and uploads a new one.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import storage as storage_svc
from app.config import settings
from app.honesty import require_honest_narrative

KINDS = ("contract", "id_copy", "certificate", "policy", "letter", "other")
FILE_TYPES = storage_svc.ATTACHMENT_CONTENT_TYPES


def _iso(value):
    return value.isoformat() if value else None


async def _hrm():
    from app import hrm

    return hrm


async def _audit(db, tenant_id, user_id, action, entity_id, details):
    hrm = await _hrm()
    await hrm._audit(db, tenant_id, user_id, action, "hrm_document", entity_id, details)


async def upload(
    db: AsyncSession, tenant_id: str, *, employee_id: str | None, title: str, kind: str, needs_ack: bool,
    confidential: bool, file: UploadFile, user_id,
) -> m.HrmDocument:
    hrm = await _hrm()
    if kind not in KINDS:
        raise HTTPException(status_code=422, detail="Choose what kind of document this is")
    if employee_id:
        await hrm._employee(db, tenant_id, employee_id)
    elif confidential:
        raise HTTPException(status_code=422, detail="A company-wide document cannot be confidential")
    if confidential and needs_ack:
        raise HTTPException(status_code=422, detail="A confidential document is not shown to staff, so it cannot ask them to accept it")
    stored = await storage_svc.save_upload(
        tenant_id=tenant_id, category="hrm_documents", upload=file, allowed_types=FILE_TYPES,
        max_bytes=int(settings.MEDIA_MAX_ATTACHMENT_BYTES),
    )
    row = m.HrmDocument(
        tenant_id=tenant_id, employee_id=employee_id, title=require_honest_narrative(title, label="title", max_length=200),
        kind=kind, storage_key=stored.key, content_type=stored.content_type, size=stored.size,
        filename=stored.original_filename, needs_ack=needs_ack, confidential=confidential, uploaded_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_document_uploaded", row.id, {"employee_id": employee_id, "kind": kind, "title": row.title})
    if needs_ack:
        from app import hrm_notify

        words = f"Please read and accept: {row.title}."
        if employee_id:
            await hrm_notify.to_person(db, tenant_id, await db.get(m.HrmEmployee, employee_id), "Document to read", words, entity_type="hrm_document", entity_id=row.id)
        else:
            for person in await hrm.list_employees(db, tenant_id):
                await hrm_notify.to_person(db, tenant_id, person, "Document to read", words, entity_type="hrm_document", entity_id=row.id)
    return row


async def _acks(db, document_id) -> list[m.HrmDocumentAck]:
    return list((await db.execute(select(m.HrmDocumentAck).where(m.HrmDocumentAck.document_id == document_id))).scalars())


async def serialize(db: AsyncSession, row: m.HrmDocument, *, for_employee: m.HrmEmployee | None = None) -> dict:
    acks = await _acks(db, row.id)
    out = {
        "id": row.id, "employee_id": row.employee_id, "company_wide": row.employee_id is None, "title": row.title,
        "kind": row.kind, "filename": row.filename, "content_type": row.content_type, "size": row.size,
        "needs_ack": bool(row.needs_ack), "confidential": bool(row.confidential), "archived": bool(row.archived_at),
        "created_at": _iso(row.created_at),
    }
    if for_employee is not None:
        mine = next((a for a in acks if a.employee_id == for_employee.id), None)
        out["accepted_at"] = _iso(mine.acknowledged_at) if mine else None
    else:
        out["accepted"] = [{"employee_id": a.employee_id, "name": a.typed_name, "at": _iso(a.acknowledged_at)} for a in acks]
    return out


async def for_person(db: AsyncSession, tenant_id: str, employee_id: str, *, include_confidential: bool) -> list[m.HrmDocument]:
    stmt = (
        select(m.HrmDocument)
        .where(m.HrmDocument.tenant_id == tenant_id, m.HrmDocument.employee_id == employee_id)
        .order_by(m.HrmDocument.created_at.desc())
    )
    if not include_confidential:
        stmt = stmt.where(m.HrmDocument.confidential.is_(False))
    return list((await db.execute(stmt)).scalars())


async def company_wide(db: AsyncSession, tenant_id: str, *, active_only: bool = False) -> list[m.HrmDocument]:
    stmt = select(m.HrmDocument).where(m.HrmDocument.tenant_id == tenant_id, m.HrmDocument.employee_id.is_(None))
    if active_only:
        stmt = stmt.where(m.HrmDocument.archived_at.is_(None))
    return list((await db.execute(stmt.order_by(m.HrmDocument.created_at.desc()))).scalars())


async def mine(db: AsyncSession, tenant_id: str, me: m.HrmEmployee) -> list[dict]:
    rows = [r for r in await for_person(db, tenant_id, me.id, include_confidential=False) if not r.archived_at]
    rows += await company_wide(db, tenant_id, active_only=True)
    return [await serialize(db, r, for_employee=me) for r in rows]


async def get(db: AsyncSession, tenant_id: str, document_id: str) -> m.HrmDocument:
    row = await db.get(m.HrmDocument, document_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


def may_open(row: m.HrmDocument, *, me: m.HrmEmployee | None, hr_officer: bool, hr_manager: bool) -> bool:
    if row.confidential:
        return hr_manager
    if hr_officer or hr_manager:
        return True
    if row.archived_at:
        return False
    return row.employee_id is None or (me is not None and row.employee_id == me.id)


async def acknowledge(db: AsyncSession, tenant_id: str, document_id: str, me: m.HrmEmployee, typed_name: str, *, user_id, ip: str | None) -> m.HrmDocumentAck:
    row = await get(db, tenant_id, document_id)
    if not may_open(row, me=me, hr_officer=False, hr_manager=False) or not row.needs_ack:
        raise HTTPException(status_code=404, detail="Document not found")
    if " ".join(typed_name.split()).lower() != " ".join((me.full_name or "").split()).lower():
        raise HTTPException(status_code=422, detail="Type your full name exactly as it is on your staff record")
    done = (
        await db.execute(select(m.HrmDocumentAck).where(m.HrmDocumentAck.document_id == row.id, m.HrmDocumentAck.employee_id == me.id))
    ).scalar_one_or_none()
    if done is not None:
        return done
    ack = m.HrmDocumentAck(
        tenant_id=tenant_id, document_id=row.id, employee_id=me.id, user_id=user_id, typed_name=" ".join(typed_name.split()),
        acknowledged_at=datetime.utcnow(), ip_address=(ip or "")[:64] or None,
    )
    db.add(ack)
    await db.flush()
    await _audit(db, tenant_id, user_id, "hrm_document_accepted", row.id, {"employee_id": me.id})
    return ack


async def outstanding(db: AsyncSession, tenant_id: str, document_id: str) -> list[dict]:
    """For a company policy: who has accepted it and who has not."""
    hrm = await _hrm()
    row = await get(db, tenant_id, document_id)
    done = {a.employee_id: a for a in await _acks(db, row.id)}
    people = [await hrm._employee(db, tenant_id, row.employee_id)] if row.employee_id else await hrm.list_employees(db, tenant_id)
    return [
        {"employee_id": p.id, "name": p.full_name, "accepted_at": _iso(done[p.id].acknowledged_at) if p.id in done else None}
        for p in people
    ]


async def archive(db: AsyncSession, tenant_id: str, document_id: str, *, user_id) -> m.HrmDocument:
    row = await get(db, tenant_id, document_id)
    if row.archived_at is None:
        row.archived_at = datetime.utcnow()
        await db.flush()
        await _audit(db, tenant_id, user_id, "hrm_document_archived", row.id, {"title": row.title})
    return row


async def waiting_count(db: AsyncSession, tenant_id: str, me: m.HrmEmployee) -> int:
    rows = [r for r in await mine(db, tenant_id, me) if r["needs_ack"] and not r.get("accepted_at")]
    return len(rows)
