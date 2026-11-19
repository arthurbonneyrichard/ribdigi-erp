"""Routes for the case file (see hrm_case_work). Managers only, except a person's own appeal."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_case_work as cw
from app import storage as storage_svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])
Read = Depends(require_permission("hrm", "read"))
Write = Depends(require_permission("hrm", "write"))


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _mgr(claims) -> None:
    svc.job(claims, "cases")
    if not svc.runs_hr(claims):
        raise HTTPException(status_code=403, detail={"code": "HRM_ROLE_JOB", "message": "Cases are for HR managers."})


class _B(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoteBody(_B):
    note: str = Field(min_length=2, max_length=8000)


class SuspensionBody(_B):
    starts_on: date
    ends_on: date | None = None
    note: str = Field(min_length=2, max_length=2000)


class AppealBody(_B):
    reason: str = Field(min_length=2, max_length=4000)


class DecisionBody(_B):
    outcome: Literal["upheld", "rejected"]
    note: str = Field(min_length=2, max_length=4000)


@router.get("/cases/{case_id}/events")
async def case_timeline(case_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    _mgr(claims)
    case = await cw._case(db, claims["tenant_id"], case_id)
    return _env({"events": await cw.timeline(db, claims["tenant_id"], case_id), "appeal": await cw.appeal_status(db, claims["tenant_id"], case)})


@router.post("/cases/{case_id}/notes")
async def case_note(case_id: UuidIdValue, body: NoteBody, claims=Write, db: AsyncSession = Depends(get_db)):
    _mgr(claims)
    out = await cw.add_note(db, claims["tenant_id"], case_id, body.note, claims.get("sub"))
    await db.commit()
    return _env(out, "Note added")


@router.post("/cases/{case_id}/evidence")
async def case_evidence(
    case_id: UuidIdValue, file: UploadFile = File(...), note: str = Form(..., min_length=2, max_length=500),
    claims=Write, db: AsyncSession = Depends(get_db),
):
    _mgr(claims)
    out = await cw.add_evidence(db, claims["tenant_id"], case_id, note, file, claims.get("sub"))
    await db.commit()
    return _env(out, "Evidence filed")


@router.get("/cases/evidence/{event_id}/file")
async def case_evidence_file(event_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    _mgr(claims)
    e = await cw.evidence_file(db, claims["tenant_id"], event_id)
    return storage_svc.media_response(e.storage_key, tenant_id=claims["tenant_id"])


@router.post("/cases/{case_id}/suspension")
async def case_suspension(case_id: UuidIdValue, body: SuspensionBody, claims=Write, db: AsyncSession = Depends(get_db)):
    _mgr(claims)
    out = await cw.add_suspension(db, claims["tenant_id"], case_id, body.starts_on, body.ends_on, body.note, claims.get("sub"))
    await db.commit()
    return _env(out, "Suspension recorded")


@router.post("/cases/{case_id}/appeal")
async def hr_lodge_appeal(case_id: UuidIdValue, body: AppealBody, claims=Write, db: AsyncSession = Depends(get_db)):
    _mgr(claims)
    out = await cw.lodge_appeal(db, claims["tenant_id"], case_id, body.reason, claims.get("sub"))
    await db.commit()
    return _env(out, "Appeal recorded")


@router.post("/cases/{case_id}/appeal/decision")
async def case_appeal_decision(case_id: UuidIdValue, body: DecisionBody, claims=Write, db: AsyncSession = Depends(get_db)):
    _mgr(claims)
    out = await cw.decide_appeal(db, claims["tenant_id"], case_id, body.outcome, body.note, claims.get("sub"))
    await db.commit()
    return _env(out, "Appeal decided")


@router.get("/me/cases/{case_id}/appeal")
async def my_appeal_status(case_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    case = await cw._case(db, claims["tenant_id"], case_id)
    if case.employee_id != me.id:
        raise HTTPException(status_code=404, detail="Case not found")
    return _env(await cw.appeal_status(db, claims["tenant_id"], case))


@router.post("/me/cases/{case_id}/appeal")
async def my_lodge_appeal(case_id: UuidIdValue, body: AppealBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    out = await cw.lodge_appeal(db, claims["tenant_id"], case_id, body.reason, claims.get("sub"), employee_id=me.id)
    await db.commit()
    return _env(out, "Appeal sent to HR")
