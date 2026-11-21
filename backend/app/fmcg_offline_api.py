"""FMCG offline sync routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_offline as svc
from app.db import get_db
from app.security import require_permission

router = APIRouter(prefix="/fmcg/offline", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ref: Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")]
    kind: Literal["shelf_audit", "competitor_price", "complaint", "pod"]
    captured_at: datetime
    payload: dict[str, Any]


class SyncBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[Action] = Field(min_length=1, max_length=50)


@router.post("/sync")
async def offline_sync(payload: SyncBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)):
    results = await svc.sync(db, claims=claims, actions=[a.model_dump() for a in payload.actions])
    await db.commit()
    return _env({"results": results, "saved": sum(1 for r in results if r["status"] == "ok"), "duplicates": sum(1 for r in results if r["status"] == "duplicate"),
                 "failed": sum(1 for r in results if r["status"] == "failed")})


@router.get("/log")
async def offline_log(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    mine = None if str(claims.get("role") or "") in svc.MANAGERS else claims.get("sub")
    return _env(await svc.log(db, tenant_id=claims["tenant_id"], user_id=mine))
