"""Routes for gym member files and the printable card."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_files as svc
from app import storage as storage_svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


def _allowed_kinds(claims) -> set[str]:
    """Only the kinds this role's jobs cover: the front desk never sees progress photos, a trainer never sees IDs."""
    out = set()
    for kind, area in svc.KINDS.items():
        try:
            base.job(claims, area)
            out.add(kind)
        except HTTPException:
            pass
    return out


@router.post("/members/{member_id}/files")
async def file_add(
    member_id: UuidIdValue,
    kind: Literal["photo", "id_document", "waiver", "progress_photo"] = Form(...),
    file: UploadFile = File(...),
    claims=Write,
    db: AsyncSession = Depends(get_db),
):
    base.job(claims, svc.area_for(kind))
    data = await svc.add_file(db, claims["tenant_id"], member_id, kind=kind, upload=file, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "File saved")


@router.get("/members/{member_id}/files")
async def files(member_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    kinds = _allowed_kinds(claims)
    if not kinds:
        base.job(claims, "members")
    return _env(await svc.list_files(db, claims["tenant_id"], member_id, kinds=kinds))


@router.get("/files/{file_id}")
async def file_get(file_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    row = await svc.get_file(db, claims["tenant_id"], file_id)
    base.job(claims, svc.area_for(row.kind))
    return storage_svc.media_response(row.storage_key, tenant_id=claims["tenant_id"], as_attachment=row.kind in ("id_document", "waiver"))


@router.delete("/files/{file_id}")
async def file_delete(file_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    row = await svc.get_file(db, claims["tenant_id"], file_id)
    base.job(claims, svc.area_for(row.kind))
    data = await svc.delete_file(db, claims["tenant_id"], file_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "File removed")


@router.post("/members/{member_id}/card", response_class=HTMLResponse)
async def card(member_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    page = await svc.print_card(db, claims["tenant_id"], member_id, user_id=claims.get("sub"))
    await db.commit()
    return HTMLResponse(page)
