"""Gym nutrition: member plans (targets and meals) and a daily intake log.

Guidance recorded by staff, not medical advice. Rows are tenant-scoped; one log per plan per day.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.gym import _audit, _member
from app.honesty import optional_honest_narrative, require_honest_narrative

_TARGETS = ("calories", "protein_g", "carbs_g", "fat_g", "water_ml")


def present_log(row: m.GymNutritionLog) -> dict:
    return {"id": row.id, "logged_on": row.logged_on.isoformat(), **{f: getattr(row, f) for f in _TARGETS}}


async def _plan(db, tenant_id: str, plan_id: str, *, lock: bool = False) -> m.GymNutritionPlan:
    stmt = select(m.GymNutritionPlan).where(m.GymNutritionPlan.id == plan_id, m.GymNutritionPlan.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found")
    return row


async def present_plan(db: AsyncSession, row: m.GymNutritionPlan) -> dict:
    member = await db.get(m.GymMember, row.member_id)
    logs = (
        await db.execute(
            select(m.GymNutritionLog)
            .where(m.GymNutritionLog.plan_id == row.id, m.GymNutritionLog.tenant_id == row.tenant_id)
            .order_by(m.GymNutritionLog.logged_on.desc())
            .limit(30)
        )
    ).scalars().all()
    return {
        "id": row.id, "name": row.name, "status": row.status, "member_id": row.member_id,
        "member_name": member.full_name if member else "", "allergies": row.allergies, "preferences": row.preferences,
        "meals": row.meals, "starts_on": row.starts_on.isoformat(), "ends_on": row.ends_on.isoformat() if row.ends_on else None,
        "targets": {f: getattr(row, f) for f in _TARGETS}, "logs": [present_log(x) for x in logs],
    }


async def create_plan(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    member = await _member(db, tenant_id, payload.member_id)
    if payload.ends_on and payload.ends_on < payload.starts_on:
        raise HTTPException(status_code=422, detail="The plan cannot end before it starts")
    if all(getattr(payload, f) is None for f in _TARGETS) and not payload.meals:
        raise HTTPException(status_code=422, detail="Give at least one target or describe the meals")
    # One live plan per member: finish or cancel the old one first, so two plans never disagree.
    live = (
        await db.execute(
            select(m.GymNutritionPlan.id)
            .where(m.GymNutritionPlan.member_id == member.id, m.GymNutritionPlan.tenant_id == tenant_id, m.GymNutritionPlan.status == "active")
            .with_for_update()
        )
    ).first()
    if live:
        raise HTTPException(status_code=409, detail=f"{member.full_name} already has an active nutrition plan")
    row = m.GymNutritionPlan(
        tenant_id=tenant_id, member_id=member.id, created_by=user_id, starts_on=payload.starts_on, ends_on=payload.ends_on,
        name=require_honest_narrative(payload.name, label="plan name", max_length=150),
        allergies=optional_honest_narrative(payload.allergies, label="allergies", max_length=300),
        preferences=optional_honest_narrative(payload.preferences, label="preferences", max_length=300),
        meals=optional_honest_narrative(payload.meals, label="meals", max_length=4000),
        **{f: getattr(payload, f) for f in _TARGETS},
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "nutrition_plan_created", "gym_nutrition_plan", row.id, {"member_id": member.id})
    return await present_plan(db, row)


async def list_plans(db: AsyncSession, tenant_id: str, *, member_id: str | None = None) -> list[dict]:
    stmt = select(m.GymNutritionPlan).where(m.GymNutritionPlan.tenant_id == tenant_id).order_by(m.GymNutritionPlan.created_at.desc())
    if member_id:
        stmt = stmt.where(m.GymNutritionPlan.member_id == member_id)
    return [await present_plan(db, r) for r in (await db.execute(stmt)).scalars().all()]


async def set_status(db: AsyncSession, tenant_id: str, plan_id: str, *, status: str, user_id) -> dict:
    row = await _plan(db, tenant_id, plan_id, lock=True)
    if row.status != "active":
        raise HTTPException(status_code=409, detail=f"This plan is already {row.status}")
    row.status = status
    await _audit(db, tenant_id, user_id, f"nutrition_plan_{status}", "gym_nutrition_plan", row.id, {})
    return await present_plan(db, row)


async def log_intake(db: AsyncSession, tenant_id: str, plan_id: str, payload, *, user_id) -> dict:
    plan = await _plan(db, tenant_id, plan_id, lock=True)
    if plan.status != "active":
        raise HTTPException(status_code=409, detail="This plan is not active")
    day = payload.logged_on or date.today()
    if day > date.today():
        raise HTTPException(status_code=422, detail="Intake cannot be logged in the future")
    if day < plan.starts_on:
        raise HTTPException(status_code=422, detail="That is before the plan started")
    if all(getattr(payload, f) is None for f in _TARGETS):
        raise HTTPException(status_code=422, detail="Enter at least one figure")
    clash = (
        await db.execute(select(m.GymNutritionLog.id).where(m.GymNutritionLog.plan_id == plan.id, m.GymNutritionLog.logged_on == day))
    ).first()
    if clash:
        raise HTTPException(status_code=409, detail="That day is already logged")
    db.add(
        m.GymNutritionLog(
            tenant_id=tenant_id, plan_id=plan.id, member_id=plan.member_id, logged_on=day, recorded_by=user_id,
            **{f: getattr(payload, f) for f in _TARGETS},
        )
    )
    await db.flush()
    await _audit(db, tenant_id, user_id, "nutrition_logged", "gym_nutrition_plan", plan.id, {"on": day.isoformat()})
    return await present_plan(db, plan)
