"""FMCG batch, expiry and recall routes. Managers and admins only (rep and driver jobs exclude "batches")."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_batches as svc
from app import fmcg_orders
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg", tags=["fmcg"])

Qty = Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)]
Text = Annotated[str, Field(min_length=3, max_length=1000)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    warn_days: list[Annotated[int, Field(ge=1, le=365)]] = Field(min_length=1, max_length=6)


class HoldBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Text


class WriteOffBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Qty
    reason_code: Literal["expiry", "damage", "recall", "other"]
    reason: Text


class RecallBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=3, max_length=200)]
    reason: Text
    batch_ids: list[UuidIdValue] = Field(min_length=1, max_length=50)


class RecoverBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: UuidIdValue
    quantity: Qty


def _manager(claims, area: str = "batches") -> None:
    fmcg_orders.job(claims, area)


@router.get("/batches")
async def fmcg_batches(
    status: Literal["all", "ok", "near", "expired", "held"] = "all",
    q: Annotated[str | None, Query(max_length=120)] = None,
    claims=Depends(require_permission("fmcg", "read")),
    db: AsyncSession = Depends(get_db),
):
    _manager(claims, "batches_read")
    return _env(await svc.list_batches(db, tenant_id=claims["tenant_id"], status=status, q=q))


@router.get("/batch-policy")
async def fmcg_batch_policy(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    _manager(claims, "batches_read")
    return _env(await svc.get_policy(db, claims["tenant_id"]))


@router.put("/batch-policy")
async def fmcg_batch_policy_save(
    payload: PolicyBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    _manager(claims, "batches")
    data = await svc.set_policy(db, claims["tenant_id"], warn_days=payload.warn_days, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/batches/{batch_id}/hold")
async def fmcg_batch_hold(
    batch_id: UuidIdValue, payload: HoldBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    _manager(claims, "batches_hold")
    data = await svc.hold_batch(db, tenant_id=claims["tenant_id"], batch_id=batch_id, reason=payload.reason, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Batch on hold")


@router.post("/batches/{batch_id}/release")
async def fmcg_batch_release(
    batch_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    _manager(claims, "batches_hold")
    data = await svc.release_batch(db, tenant_id=claims["tenant_id"], batch_id=batch_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Batch released")


@router.post("/batches/{batch_id}/write-off")
async def fmcg_batch_write_off(
    batch_id: UuidIdValue, payload: WriteOffBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    _manager(claims, "batches")
    data = await svc.write_off(
        db, tenant_id=claims["tenant_id"], batch_id=batch_id, quantity=payload.quantity,
        reason_code=payload.reason_code, reason=payload.reason, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Written off")


@router.get("/recalls")
async def fmcg_recalls(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    _manager(claims, "batches")
    return _env(await svc.list_recalls(db, tenant_id=claims["tenant_id"]))


@router.post("/recalls")
async def fmcg_recall_open(
    payload: RecallBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    _manager(claims, "batches")
    data = await svc.create_recall(
        db, tenant_id=claims["tenant_id"], title=payload.title, reason=payload.reason,
        batch_ids=payload.batch_ids, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Recall opened")


@router.get("/recalls/{recall_id}")
async def fmcg_recall_get(
    recall_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    _manager(claims, "batches")
    return _env(await svc.recall_detail(db, tenant_id=claims["tenant_id"], recall_id=recall_id))


@router.post("/recalls/{recall_id}/recovered")
async def fmcg_recall_recovered(
    recall_id: UuidIdValue, payload: RecoverBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    _manager(claims, "batches")
    data = await svc.record_recovery(
        db, tenant_id=claims["tenant_id"], recall_id=recall_id, batch_id=payload.batch_id,
        quantity=payload.quantity, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Recorded")


@router.post("/recalls/{recall_id}/close")
async def fmcg_recall_close(
    recall_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    _manager(claims, "batches")
    data = await svc.close_recall(db, tenant_id=claims["tenant_id"], recall_id=recall_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Recall closed")
