"""Routes for gym equipment assets. Managers only (the `correct` area)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_assets as svc
from app.db import get_db
from app.schemas import PositiveMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class AssetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    purchase_date: date
    purchase_cost: PositiveMoneyValue
    useful_life_months: Annotated[int, Field(ge=1, le=600)]
    warranty_until: date | None = None
    supplier_name: Annotated[str, Field(min_length=1, max_length=150)] | None = None


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.post("/equipment/{equipment_id}/asset")
async def asset_set(equipment_id: UuidIdValue, payload: AssetBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    data = await svc.set_asset(db, claims["tenant_id"], equipment_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/reports/equipment-assets")
async def assets(as_of: date | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.asset_report(db, claims["tenant_id"], as_of=as_of or date.today()))
