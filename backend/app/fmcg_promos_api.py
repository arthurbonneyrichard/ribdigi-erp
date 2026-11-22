"""FMCG promotion routes: create with limits and targets, approve, policy and performance. Managers only."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import fmcg_orders as orders
from app import fmcg_promos as svc
from app.db import get_db
from app.schemas import IsoDateQueryValue, NonNegativeMoneyValue, PositiveMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/fmcg/promotions", tags=["fmcg"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class TargetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["customer", "route", "territory"]
    ref_id: UuidIdValue


class PromotionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, Field(min_length=2, max_length=40)]
    name: Annotated[str, Field(min_length=2, max_length=150)]
    scheme_type: Literal["percent", "fixed", "bxgy"] = "percent"
    value: NonNegativeMoneyValue = 0
    buy_qty: Annotated[int, Field(ge=0, le=100000)] = 0
    get_qty: Annotated[int, Field(ge=0, le=100000)] = 0
    product_id: UuidIdValue | None = None
    category_id: UuidIdValue | None = None
    starts_on: IsoDateQueryValue | None = None
    ends_on: IsoDateQueryValue | None = None
    notes: Annotated[str, Field(min_length=3, max_length=500)] | None = None
    budget: PositiveMoneyValue | None = None
    max_uses: Annotated[int, Field(ge=1, le=10_000_000)] | None = None
    min_qty: Annotated[float, Field(gt=0, le=1_000_000, allow_inf_nan=False)] | None = None
    targets: list[TargetBody] = Field(default_factory=list, max_length=200)


class RejectBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=500)]


class PolicyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approval_percent: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
    approval_budget: NonNegativeMoneyValue = 0


@router.get("")
async def promo_list(
    status: Literal["pending", "approved", "rejected"] | None = None,
    claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "promotions")
    return _env(await svc.list_promotions(db, tenant_id=claims["tenant_id"], status=status))


@router.post("")
async def promo_create(
    payload: PromotionBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "promotions")
    data = await svc.create_promotion(
        db, tenant_id=claims["tenant_id"], user_id=claims.get("sub"), code=payload.code, name=payload.name,
        scheme_type=payload.scheme_type, value=float(payload.value or 0), buy_qty=payload.buy_qty,
        get_qty=payload.get_qty, product_id=payload.product_id, category_id=payload.category_id,
        starts_on=payload.starts_on, ends_on=payload.ends_on, notes=payload.notes,
        budget=float(payload.budget) if payload.budget is not None else None, max_uses=payload.max_uses,
        min_qty=payload.min_qty, targets=[(t.kind, t.ref_id) for t in payload.targets],
    )
    await db.commit()
    return _env(data, "Promotion created" if data["status"] == "approved" else "Promotion created and waiting for approval")


@router.get("/policy")
async def promo_policy(claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)):
    orders.job(claims, "promotions")
    return _env(await svc.get_policy(db, claims["tenant_id"]))


@router.put("/policy")
async def promo_policy_save(
    payload: PolicyBody, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "promotions")
    data = await svc.set_policy(
        db, claims["tenant_id"], approval_percent=payload.approval_percent,
        approval_budget=float(payload.approval_budget), user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(data, "Saved")


@router.post("/{scheme_id}/approve")
async def promo_approve(
    scheme_id: UuidIdValue, claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "promotions")
    data = await svc.approve(db, tenant_id=claims["tenant_id"], scheme_id=scheme_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Approved")


@router.post("/{scheme_id}/reject")
async def promo_reject(
    scheme_id: UuidIdValue, payload: RejectBody,
    claims=Depends(require_permission("fmcg", "write")), db: AsyncSession = Depends(get_db),
):
    orders.job(claims, "promotions")
    data = await svc.reject(
        db, tenant_id=claims["tenant_id"], scheme_id=scheme_id, reason=payload.reason, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Rejected")


@router.get("/{scheme_id}/performance")
async def promo_performance(
    scheme_id: UuidIdValue, claims=Depends(require_permission("fmcg", "read")), db: AsyncSession = Depends(get_db)
):
    orders.job(claims, "promotions")
    return _env(await svc.performance(db, tenant_id=claims["tenant_id"], scheme_id=scheme_id))
