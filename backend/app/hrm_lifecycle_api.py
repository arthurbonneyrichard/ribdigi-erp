"""Routes for onboarding/offboarding, exit interviews, benefits, career history, OKRs, custom fields
and succession (see hrm_lifecycle). Areas: people (staff file work), contracts (benefits),
reviews (OKRs, managers only); custom field set-up and succession are HR managers only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_lifecycle as lc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm", tags=["hrm"])
Read = Depends(require_permission("hrm", "read"))
Write = Depends(require_permission("hrm", "write"))


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


def _manager_only(claims) -> None:
    if not svc.runs_hr(claims):
        raise HTTPException(status_code=403, detail={"code": "HRM_ROLE_JOB", "message": "Only an HR manager can do this."})


class _B(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartBody(_B):
    kind: str


class TaskBody(_B):
    kind: str
    title: Annotated[str, Field(min_length=2, max_length=200)]
    due_on: date | None = None


class ExitBody(_B):
    held_on: date
    reason_category: str
    would_return: bool | None = None
    feedback: str | None = Field(default=None, max_length=2000)


class BenefitBody(_B):
    kind: str
    name: Annotated[str, Field(min_length=2, max_length=160)]
    provider: str | None = Field(default=None, max_length=160)
    policy_number: str | None = Field(default=None, max_length=80)
    starts_on: date
    ends_on: date | None = None
    note: str | None = Field(default=None, max_length=255)


class EndBenefitBody(_B):
    ends_on: date


class CareerBody(_B):
    kind: str
    effective_on: date
    to_job_title: str | None = Field(default=None, max_length=120)
    to_department: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=255)


class ObjectiveBody(_B):
    kind: str = "objective"
    level: str = "employee"
    period: Annotated[str, Field(min_length=2, max_length=16)] = "2026"
    title: Annotated[str, Field(min_length=2, max_length=200)]
    employee_id: UuidIdValue | None = None
    department: str | None = Field(default=None, max_length=120)
    parent_id: UuidIdValue | None = None
    unit: str | None = Field(default=None, max_length=24)
    target: float | None = Field(default=None, ge=0, le=1e12)


class ProgressBody(_B):
    current: float | None = Field(default=None, ge=0, le=1e12)
    status: str | None = None


class FieldBody(_B):
    label: Annotated[str, Field(min_length=2, max_length=80)]
    kind: str = "text"


class ValueBody(_B):
    value: str | None = Field(default=None, max_length=255)


class SuccessionBody(_B):
    position: Annotated[str, Field(min_length=2, max_length=160)]
    incumbent_id: UuidIdValue | None = None
    successor_id: UuidIdValue
    readiness: str
    note: str | None = Field(default=None, max_length=255)


# --- checklists ---


@router.get("/checklists")
async def checklist_overview(claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    return _env(await lc.overview(db, claims["tenant_id"]))


@router.get("/employees/{employee_id}/checklist/{kind}")
async def get_checklist(employee_id: UuidIdValue, kind: str, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    if kind not in lc.KINDS:
        raise HTTPException(status_code=422, detail="Choose onboarding or offboarding")
    await lc._emp(db, claims["tenant_id"], employee_id)
    return _env(await lc.checklist(db, claims["tenant_id"], employee_id, kind))


@router.post("/employees/{employee_id}/checklist")
async def start_checklist(employee_id: UuidIdValue, body: StartBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    out = await lc.start_checklist(db, claims["tenant_id"], employee_id, body.kind, claims.get("sub"))
    await db.commit()
    return _env(out, "Checklist started")


@router.post("/employees/{employee_id}/checklist/tasks")
async def add_task(employee_id: UuidIdValue, body: TaskBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    out = await lc.add_task(db, claims["tenant_id"], employee_id, body.kind, body.title, body.due_on, claims.get("sub"))
    await db.commit()
    return _env(out)


@router.post("/checklist/tasks/{task_id}/done")
async def task_done(task_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    out = await lc.set_task_done(db, claims["tenant_id"], task_id, True, claims.get("sub"))
    await db.commit()
    return _env(out)


@router.post("/checklist/tasks/{task_id}/undo")
async def task_undo(task_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    out = await lc.set_task_done(db, claims["tenant_id"], task_id, False, claims.get("sub"))
    await db.commit()
    return _env(out)


@router.put("/employees/{employee_id}/exit-interview")
async def save_exit(employee_id: UuidIdValue, body: ExitBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    out = await lc.save_exit_interview(
        db, claims["tenant_id"], employee_id, held_on=body.held_on, reason_category=body.reason_category,
        would_return=body.would_return, feedback=body.feedback, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(out, "Exit interview saved")


# --- benefits ---


@router.get("/employees/{employee_id}/benefits")
async def list_benefits(employee_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "contracts")
    await lc._emp(db, claims["tenant_id"], employee_id)
    return _env(await lc.benefits_for(db, claims["tenant_id"], employee_id))


@router.post("/employees/{employee_id}/benefits")
async def add_benefit(employee_id: UuidIdValue, body: BenefitBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "contracts")
    out = await lc.add_benefit(db, claims["tenant_id"], employee_id, user_id=claims.get("sub"), **body.model_dump())
    await db.commit()
    return _env(out, "Benefit recorded")


@router.post("/benefits/{benefit_id}/end")
async def end_benefit(benefit_id: UuidIdValue, body: EndBenefitBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "contracts")
    out = await lc.end_benefit(db, claims["tenant_id"], benefit_id, body.ends_on, claims.get("sub"))
    await db.commit()
    return _env(out)


# --- career ---


@router.get("/employees/{employee_id}/career")
async def career(employee_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    await lc._emp(db, claims["tenant_id"], employee_id)
    return _env(await lc.career_history(db, claims["tenant_id"], employee_id))


@router.post("/employees/{employee_id}/career")
async def add_career(employee_id: UuidIdValue, body: CareerBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    out = await lc.record_career_event(db, claims["tenant_id"], employee_id, user_id=claims.get("sub"), **body.model_dump())
    await db.commit()
    return _env(out, "Recorded")


# --- OKRs ---


@router.get("/objectives")
async def objectives(period: str | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    return _env(await lc.list_objectives(db, claims["tenant_id"], period=period))


@router.get("/me/objectives")
async def my_objectives(period: str | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "self")
    emp = await svc.employee_for_user(db, claims["tenant_id"], claims.get("sub"))
    return _env(await lc.list_objectives(db, claims["tenant_id"], period=period, employee_id=emp.id))


@router.post("/objectives")
async def create_objective(body: ObjectiveBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    out = await lc.create_objective(db, claims["tenant_id"], user_id=claims.get("sub"), **body.model_dump())
    await db.commit()
    return _env(out, "Saved")


@router.patch("/objectives/{objective_id}")
async def update_objective(objective_id: UuidIdValue, body: ProgressBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "reviews")
    out = await lc.update_objective(db, claims["tenant_id"], objective_id, current=body.current, status=body.status, user_id=claims.get("sub"))
    await db.commit()
    return _env(out)


# --- custom fields ---


@router.get("/custom-fields")
async def custom_fields(claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    return _env([{"id": f.id, "label": f.label, "kind": f.kind} for f in await lc.list_fields(db, claims["tenant_id"])])


@router.post("/custom-fields")
async def create_field(body: FieldBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    out = await lc.create_field(db, claims["tenant_id"], body.label, body.kind, claims.get("sub"))
    await db.commit()
    return _env(out)


@router.delete("/custom-fields/{field_id}")
async def retire_field(field_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    await lc.retire_field(db, claims["tenant_id"], field_id)
    await db.commit()
    return _env({"retired": True})


@router.get("/employees/{employee_id}/custom")
async def get_custom(employee_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    return _env(await lc.custom_values(db, claims["tenant_id"], employee_id))


@router.put("/employees/{employee_id}/custom/{field_id}")
async def set_custom(employee_id: UuidIdValue, field_id: UuidIdValue, body: ValueBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    await lc.set_custom_value(db, claims["tenant_id"], employee_id, field_id, body.value, claims.get("sub"))
    await db.commit()
    return _env(await lc.custom_values(db, claims["tenant_id"], employee_id))


# --- succession ---


@router.get("/succession")
async def succession(claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    return _env(await lc.list_succession(db, claims["tenant_id"]))


@router.post("/succession")
async def add_succession(body: SuccessionBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    out = await lc.save_succession(db, claims["tenant_id"], user_id=claims.get("sub"), **body.model_dump())
    await db.commit()
    return _env(out)


@router.delete("/succession/{row_id}")
async def remove_succession(row_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "people")
    _manager_only(claims)
    await lc.remove_succession(db, claims["tenant_id"], row_id)
    await db.commit()
    return _env({"removed": True})
