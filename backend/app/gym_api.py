"""Gym routes. The `gym` permission and the industry gate come from require_permission."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as svc
from app.db import get_db
from app.schemas import E164PhoneValue, NonNegativeMoneyValue, PartyNameValue, PositiveMoneyValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])

Method = Literal["cash", "card", "mobile_money", "bank_transfer"]
Notes = Annotated[str, Field(min_length=1, max_length=500)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class PlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=120)]
    price: PositiveMoneyValue
    duration_days: Annotated[int, Field(ge=1, le=1830)]
    visit_limit: Annotated[int, Field(ge=1, le=10000)] | None = None


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    price: PositiveMoneyValue | None = None
    is_active: bool | None = None


class MemberBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: PartyNameValue
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    emergency_contact: Annotated[str, Field(min_length=1, max_length=180)] | None = None
    notes: Notes | None = None


class SellBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UuidIdValue
    plan_id: UuidIdValue
    method: Method


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=255)]
    refund: NonNegativeMoneyValue = 0
    method: Method | None = None


class CheckInBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UuidIdValue


class ClassBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=120)]
    trainer_name: Annotated[str, Field(min_length=1, max_length=150)] | None = None
    starts_at: datetime
    capacity: Annotated[int, Field(ge=1, le=500)]


class BookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UuidIdValue


class BookingStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["booked", "attended", "no_show", "cancelled"]


class ShiftOpen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_cash: NonNegativeMoneyValue = 0


class ShiftClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    counted_cash: NonNegativeMoneyValue


def _sees_money(claims: dict) -> bool:
    return str(claims.get("role") or "") != "gym_trainer"


@router.get("/today")
async def gym_today(claims=Depends(require_permission("gym", "read")), db: AsyncSession = Depends(get_db)):
    return _env(await svc.today(db, claims["tenant_id"], money=_sees_money(claims)))


@router.get("/plans")
async def gym_plans(claims=Depends(require_permission("gym", "read")), db: AsyncSession = Depends(get_db)):
    return _env([svc.serialize_plan(r) for r in await svc.list_plans(db, claims["tenant_id"])])


@router.post("/plans")
async def gym_plan_create(
    payload: PlanBody, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "correct")
    row = await svc.create_plan(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_plan(row), "Plan added")


@router.patch("/plans/{plan_id}")
async def gym_plan_update(
    plan_id: UuidIdValue,
    payload: PlanUpdate,
    claims=Depends(require_permission("gym", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "correct")
    row = await svc.update_plan(db, claims["tenant_id"], plan_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.serialize_plan(row), "Plan saved")


@router.get("/members")
async def gym_members(
    q: Annotated[str, Query(max_length=120)] = "",
    claims=Depends(require_permission("gym", "read")),
    db: AsyncSession = Depends(get_db),
):
    rows = await svc.list_members(db, claims["tenant_id"], q=q)
    return _env([await svc.present_member(db, r) for r in rows])


@router.post("/members")
async def gym_member_create(
    payload: MemberBody, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "members")
    row = await svc.create_member(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_member(db, row), "Member added")


@router.post("/memberships")
async def gym_sell(
    payload: SellBody, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "desk")
    row = await svc.sell_membership(
        db, claims["tenant_id"], member_id=payload.member_id, plan_id=payload.plan_id,
        method=payload.method, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env(
        {"id": row.id, "membership_number": row.membership_number, "starts_on": row.starts_on.isoformat(),
         "ends_on": row.ends_on.isoformat(), "total": svc._money(row.total)},
        "Membership sold",
    )


@router.post("/memberships/{membership_id}/freeze")
async def gym_freeze(
    membership_id: UuidIdValue, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "desk")
    await svc.freeze(db, claims["tenant_id"], membership_id, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": membership_id}, "Membership frozen")


@router.post("/memberships/{membership_id}/unfreeze")
async def gym_unfreeze(
    membership_id: UuidIdValue, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "desk")
    row = await svc.unfreeze(db, claims["tenant_id"], membership_id, user_id=claims.get("sub"))
    await db.commit()
    return _env({"id": row.id, "ends_on": row.ends_on.isoformat()}, "Membership running again")


@router.post("/memberships/{membership_id}/cancel")
async def gym_cancel(
    membership_id: UuidIdValue,
    payload: CancelBody,
    claims=Depends(require_permission("gym", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "correct")
    await svc.cancel_membership(
        db, claims["tenant_id"], membership_id, reason=payload.reason, refund=payload.refund,
        method=payload.method, user_id=claims.get("sub"),
    )
    await db.commit()
    return _env({"id": membership_id}, "Membership cancelled")


@router.post("/check-ins")
async def gym_check_in(
    payload: CheckInBody, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "door")
    data = await svc.check_in(db, claims["tenant_id"], member_id=payload.member_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, data["message"])


@router.get("/check-ins")
async def gym_check_ins(claims=Depends(require_permission("gym", "read")), db: AsyncSession = Depends(get_db)):
    return _env(await svc.list_check_ins(db, claims["tenant_id"]))


@router.get("/classes")
async def gym_classes(claims=Depends(require_permission("gym", "read")), db: AsyncSession = Depends(get_db)):
    return _env([await svc.present_class(db, r) for r in await svc.list_classes(db, claims["tenant_id"])])


@router.post("/classes")
async def gym_class_create(
    payload: ClassBody, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "classes")
    row = await svc.create_class(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_class(db, row), "Class added")


@router.post("/classes/{class_id}/book")
async def gym_class_book(
    class_id: UuidIdValue,
    payload: BookBody,
    claims=Depends(require_permission("gym", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "classes")
    row = await svc.book_class(db, claims["tenant_id"], class_id, member_id=payload.member_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_class(db, row), "Booked")


@router.post("/classes/{class_id}/cancel")
async def gym_class_cancel(
    class_id: UuidIdValue, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "classes")
    await svc.cancel_class(db, claims["tenant_id"], class_id)
    await db.commit()
    return _env({"id": class_id}, "Class cancelled")


@router.post("/bookings/{booking_id}")
async def gym_booking_set(
    booking_id: UuidIdValue,
    payload: BookingStatus,
    claims=Depends(require_permission("gym", "write")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "classes")
    row = await svc.set_booking(db, claims["tenant_id"], booking_id, status=payload.status)
    await db.commit()
    return _env(await svc.present_class(db, row), "Saved")


@router.get("/till/shift")
async def gym_shift(claims=Depends(require_permission("gym", "read")), db: AsyncSession = Depends(get_db)):
    svc.job(claims, "desk")
    shift = await svc.current_shift(db, claims["tenant_id"])
    return _env(await svc.present_shift(db, claims["tenant_id"], shift) if shift else None)


@router.post("/till/shift/open")
async def gym_shift_open(
    payload: ShiftOpen, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "desk")
    row = await svc.open_shift(db, claims["tenant_id"], opening_cash=payload.opening_cash, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_shift(db, claims["tenant_id"], row), "Till open")


@router.post("/till/shift/close")
async def gym_shift_close(
    payload: ShiftClose, claims=Depends(require_permission("gym", "write")), db: AsyncSession = Depends(get_db)
):
    svc.job(claims, "desk")
    row = await svc.close_shift(db, claims["tenant_id"], counted_cash=payload.counted_cash, user_id=claims.get("sub"))
    await db.commit()
    return _env(await svc.present_shift(db, claims["tenant_id"], row), "Till closed")


@router.get("/reports")
async def gym_reports(
    start_date: date | None = None,
    end_date: date | None = None,
    claims=Depends(require_permission("gym", "read")),
    db: AsyncSession = Depends(get_db),
):
    svc.job(claims, "correct")
    end = end_date or date.today()
    start = start_date or end - timedelta(days=29)
    data = await svc.period_numbers(db, claims["tenant_id"], start=start, end=end)
    data["expiring"] = await svc.expiring(db, claims["tenant_id"], days=30)
    data["active_members"] = await svc.active_members(db, claims["tenant_id"])
    return _env(data)
