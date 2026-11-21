"""Routes for the FMCG field workforce (see hrm_field)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_field as field
from app.db import get_db
from app.schemas import NonNegativeMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _fmcg(claims) -> None:
    from app import packages as packages_svc

    svc.job(claims, "people")
    if packages_svc.canonicalize_industry(claims.get("industry")) != "fmcg":
        raise HTTPException(status_code=403, detail={"code": "HRM_AREA_OFF", "message": "Field workforce is part of FMCG HR."})


class FieldBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_role: str
    monthly_sales_target: NonNegativeMoneyValue | None = None


@router.get("/field-workforce")
async def field_workforce(
    period: Annotated[str | None, Query(pattern=r"^20\d{2}-(0[1-9]|1[0-2])$")] = None,
    claims=Depends(require_permission("hrm", "read")),
    db: AsyncSession = Depends(get_db),
):
    _fmcg(claims)
    p = period or date.today().strftime("%Y-%m")
    return _env(await field.workforce(db, claims["tenant_id"], p, with_pay=svc.sees_pay(claims)))


@router.put("/employees/{employee_id}/field-profile")
async def save_field_profile(
    employee_id: UuidIdValue, body: FieldBody, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)
):
    _fmcg(claims)
    out = await field.set_profile(
        db, claims["tenant_id"], employee_id, field_role=body.field_role,
        monthly_sales_target=body.monthly_sales_target, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(out, "Saved")


@router.delete("/employees/{employee_id}/field-profile")
async def remove_field_profile(employee_id: UuidIdValue, claims=Depends(require_permission("hrm", "write")), db: AsyncSession = Depends(get_db)):
    _fmcg(claims)
    await field.remove_profile(db, claims["tenant_id"], employee_id)
    await db.commit()
    return _env({"removed": True})
