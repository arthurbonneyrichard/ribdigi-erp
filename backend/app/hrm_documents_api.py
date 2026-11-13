"""Routes for documents on staff files and company policies (see hrm_documents)."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_documents as docs
from app import storage as storage_svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])
Kind = Literal["contract", "id_copy", "certificate", "policy", "letter", "other"]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class AcceptBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    typed_name: Annotated[str, Field(min_length=2, max_length=150)]


async def _upload(db, claims, employee_id, title, kind, needs_ack, confidential, file):
    svc.job(claims, "people")
    if confidential and not svc.runs_hr(claims):
        raise HTTPException(status_code=403, detail="Only an HR manager can file a confidential document")
    row = await docs.upload(
        db, claims["tenant_id"], employee_id=employee_id, title=title, kind=kind, needs_ack=needs_ack,
        confidential=confidential, file=file, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(await docs.serialize(db, row), "Document filed")


@router.post("/employees/{employee_id}/documents")
async def add_staff_document(
    employee_id: UuidIdValue,
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=200),
    kind: Kind = Form("other"),
    needs_ack: bool = Form(False),
    confidential: bool = Form(False),
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    return await _upload(db, claims, employee_id, title, kind, needs_ack, confidential, file)


@router.post("/documents")
async def add_company_document(
    file: UploadFile = File(...),
    title: str = Form(..., min_length=2, max_length=200),
    kind: Kind = Form("policy"),
    needs_ack: bool = Form(True),
    claims=Depends(require_permission("hrm", "write")),
    db: AsyncSession = Depends(get_db),
):
    return await _upload(db, claims, None, title, kind, needs_ack, False, file)


@router.get("/employees/{employee_id}/documents")
async def staff_documents(employee_id: UuidIdValue, claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    rows = await docs.for_person(db, claims["tenant_id"], employee_id, include_confidential=svc.runs_hr(claims))
    return _env([await docs.serialize(db, r) for r in rows])


@router.get("/documents")
async def company_documents(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    return _env([await docs.serialize(db, r) for r in await docs.company_wide(db, claims["tenant_id"])])


@router.get("/documents/{document_id}/accepted")
async def document_accepted(document_id: UuidIdValue, claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    return _env(await docs.outstanding(db, claims["tenant_id"], document_id))


@router.post("/documents/{document_id}/archive")
async def archive_document(document_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    row = await docs.get(db, claims["tenant_id"], document_id)
    if row.confidential and not svc.runs_hr(claims):
        raise HTTPException(status_code=404, detail="Document not found")
    row = await docs.archive(db, claims["tenant_id"], document_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await docs.serialize(db, row), "Archived")


@router.get("/documents/{document_id}/file")
async def open_document(document_id: UuidIdValue, claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    """HR opens any file it may see; staff open their own and company policies."""
    row = await docs.get(db, claims["tenant_id"], document_id)
    hr_manager = svc.runs_hr(claims)
    try:
        svc.job(claims, "people")
        hr_officer = True
    except HTTPException:
        hr_officer = False
    me = await svc._user_employee(db, claims["tenant_id"], claims.get("sub"))
    if not docs.may_open(row, me=me, hr_officer=hr_officer, hr_manager=hr_manager):
        raise HTTPException(status_code=404, detail="Document not found")
    return storage_svc.media_response(row.storage_key, tenant_id=claims["tenant_id"])


class HeadcountBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: Annotated[str, Field(min_length=1, max_length=120)]
    planned: Annotated[int, Field(ge=0, le=100000)] | None = None


@router.get("/org-chart")
async def org_chart(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    from app import hrm_org

    return _env(await hrm_org.org_chart(db, claims["tenant_id"]))


@router.get("/headcount")
async def headcount(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    from app import hrm_org

    return _env(await hrm_org.headcount(db, claims["tenant_id"]))


@router.put("/headcount")
async def set_headcount(payload: HeadcountBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    if not svc.runs_hr(claims):
        raise HTTPException(status_code=403, detail="Headcount is planned by an HR manager or the company admin")
    from app import hrm_org

    await hrm_org.set_plan(db, claims["tenant_id"], department=payload.department, planned=payload.planned, user_id=claims.get("sub"))
    await db.commit()
    return _env(await hrm_org.headcount(db, claims["tenant_id"]), "Headcount plan saved")


@router.get("/me/documents")
async def my_documents(claims=Depends(require_permission("hrm", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    return _env(await docs.mine(db, claims["tenant_id"], me))


@router.post("/me/documents/{document_id}/accept")
async def accept_document(
    document_id: UuidIdValue, payload: AcceptBody, request: Request,
    claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "self")
    me = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    ip = request.client.host if request.client else None
    await docs.acknowledge(db, claims["tenant_id"], document_id, me, payload.typed_name, user_id=claims.get("sub"), ip=ip)
    await db.commit()
    return _env(await docs.serialize(db, await docs.get(db, claims["tenant_id"], document_id), for_employee=me), "Accepted")
