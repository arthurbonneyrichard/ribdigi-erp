"""Hospital patient desk: patients and visits.

Not a diagnosis coder, insurer, operating theatre, or pharmacist-license system.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import optional_honest_narrative, require_honest_narrative
from app.packages import canonicalize_industry
from app.rbac import is_platform_role


def assert_hospital(claims: dict) -> None:
    if is_platform_role(claims.get("role")):
        return
    industry = canonicalize_industry(claims.get("industry"))
    if industry != "hospital":
        raise HTTPException(
            status_code=403,
            detail={
                "code": "INDUSTRY_MODULE_DISABLED",
                "message": "Hospital visits are only available for hospital tenants.",
            },
        )


def serialize_patient(row: m.HospitalPatient) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "phone": row.phone,
        "notes": row.notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_encounter(row: m.HospitalEncounter) -> dict:
    return {
        "id": row.id,
        "patient_id": row.patient_id,
        "reason": row.reason,
        "status": row.status,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
    }


async def create_patient(
    db: AsyncSession,
    *,
    tenant_id: str,
    name: str,
    phone: str | None,
    notes: str | None,
) -> m.HospitalPatient:
    row = m.HospitalPatient(
        tenant_id=tenant_id,
        name=require_honest_narrative(name, label="patient name", max_length=180),
        phone=(phone or "").strip() or None,
        notes=optional_honest_narrative(notes, label="patient notes"),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def list_patients(db: AsyncSession, tenant_id: str) -> list[m.HospitalPatient]:
    return (
        await db.execute(
            select(m.HospitalPatient)
            .where(m.HospitalPatient.tenant_id == tenant_id)
            .order_by(m.HospitalPatient.created_at.desc())
        )
    ).scalars().all()


async def open_encounter(
    db: AsyncSession,
    *,
    tenant_id: str,
    patient_id: str,
    reason: str,
) -> m.HospitalEncounter:
    patient = (
        await db.execute(
            select(m.HospitalPatient).where(
                m.HospitalPatient.id == patient_id,
                m.HospitalPatient.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    row = m.HospitalEncounter(
        tenant_id=tenant_id,
        patient_id=patient.id,
        reason=require_honest_narrative(reason, label="visit reason", max_length=240),
        status="open",
        opened_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def close_encounter(
    db: AsyncSession, *, tenant_id: str, encounter_id: str
) -> m.HospitalEncounter:
    row = (
        await db.execute(
            select(m.HospitalEncounter).where(
                m.HospitalEncounter.id == encounter_id,
                m.HospitalEncounter.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Visit not found")
    if row.status != "open":
        raise HTTPException(status_code=409, detail="Visit is already closed")
    row.status = "closed"
    row.closed_at = datetime.utcnow()
    await db.flush()
    return row
