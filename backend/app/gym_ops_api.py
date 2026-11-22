"""Routes for gym trainers, sessions, lockers, equipment and guests."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_ops as svc
from app.db import get_db
from app.schemas import E164PhoneValue, NonNegativeMoneyValue, PartyNameValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])
Text = Annotated[str, Field(min_length=1, max_length=500)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class TrainerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: PartyNameValue
    phone: E164PhoneValue | None = None
    specialization: Annotated[str, Field(min_length=1, max_length=150)] | None = None
    session_price: NonNegativeMoneyValue = 0


class SessionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trainer_id: UuidIdValue
    member_id: UuidIdValue
    starts_at: datetime
    minutes: int = 60
    notes: Text | None = None


class SessionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "cancelled", "no_show"]


class LockerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: Annotated[str, Field(min_length=1, max_length=20)]


Method = Literal["cash", "card", "mobile_money", "bank_transfer"]


class AssignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UuidIdValue
    rental_days: Annotated[int, Field(ge=1, le=366)] | None = None
    fee: NonNegativeMoneyValue = 0
    method: Method | None = None


class RenewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rental_days: Annotated[int, Field(ge=1, le=366)]
    fee: NonNegativeMoneyValue = 0
    method: Method | None = None


class EquipmentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=150)]
    category: Annotated[str, Field(min_length=1, max_length=80)] | None = None
    serial_number: Annotated[str, Field(min_length=1, max_length=80)] | None = None


class FaultBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fault: Annotated[str, Field(min_length=3, max_length=500)]


class FixBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: Annotated[str, Field(min_length=3, max_length=500)]
    retire: bool = False


class GuestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guest_name: PartyNameValue
    phone: E164PhoneValue | None = None
    host_member_id: UuidIdValue | None = None
    fee: NonNegativeMoneyValue = 0
    method: Method | None = None


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.get("/trainers")
async def trainers(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    return _env([svc.present_trainer(r) for r in await svc.list_trainers(db, claims["tenant_id"])])


@router.post("/trainers")
async def trainer_add(payload: TrainerBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "people")
    row = await svc.create_trainer(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.present_trainer(row), "Trainer added")


@router.get("/training-sessions")
async def sessions(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    return _env(await svc.list_sessions(db, claims["tenant_id"]))


@router.post("/training-sessions")
async def session_book(payload: SessionBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    data = await svc.book_session(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Session booked")


@router.post("/training-sessions/{session_id}")
async def session_set(session_id: UuidIdValue, payload: SessionStatus, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    data = await svc.set_session(db, claims["tenant_id"], session_id, status=payload.status, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/lockers")
async def lockers(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "lockers")
    return _env(await svc.list_lockers(db, claims["tenant_id"]))


@router.post("/lockers")
async def locker_add(payload: LockerBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    row = await svc.create_locker(db, claims["tenant_id"], number=payload.number)
    await db.commit()
    return _env(svc.present_locker(row, None), "Locker added")


@router.post("/lockers/{locker_id}/assign")
async def locker_assign(locker_id: UuidIdValue, payload: AssignBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "lockers")
    data = await svc.assign_locker(
        db, claims["tenant_id"], locker_id, member_id=payload.member_id, user_id=claims.get("sub"),
        rental_days=payload.rental_days, fee=payload.fee, method=payload.method,
    )
    await db.commit()
    return _env(data, "Locker given")


@router.post("/lockers/{locker_id}/renew")
async def locker_renew(locker_id: UuidIdValue, payload: RenewBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "lockers")
    data = await svc.renew_locker(
        db, claims["tenant_id"], locker_id, rental_days=payload.rental_days, fee=payload.fee, method=payload.method, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Rental extended")


@router.post("/lockers/{locker_id}/release")
async def locker_release(locker_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "lockers")
    data = await svc.release_locker(db, claims["tenant_id"], locker_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Locker free")


@router.get("/equipment")
async def equipment(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    return _env(await svc.list_equipment(db, claims["tenant_id"]))


@router.post("/equipment")
async def equipment_add(payload: EquipmentBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    row = await svc.create_equipment(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.present_equipment(row), "Equipment added")


@router.post("/equipment/{equipment_id}/faults")
async def fault_report(equipment_id: UuidIdValue, payload: FaultBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    data = await svc.report_fault(db, claims["tenant_id"], equipment_id, fault=payload.fault, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Fault logged")


@router.get("/maintenance")
async def faults_open(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    return _env(await svc.list_faults(db, claims["tenant_id"]))


@router.post("/maintenance/{ticket_id}/close")
async def fault_close(ticket_id: UuidIdValue, payload: FixBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "equipment")
    data = await svc.close_fault(
        db, claims["tenant_id"], ticket_id, resolution=payload.resolution, retire=payload.retire, user_id=claims.get("sub")
    )
    await db.commit()
    return _env(data, "Ticket closed")


@router.get("/guests")
async def guests(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "guests")
    return _env(await svc.list_guests(db, claims["tenant_id"]))


@router.post("/guests")
async def guest_add(payload: GuestBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "guests")
    data = await svc.register_guest(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Guest in")


@router.post("/guests/{visit_id}/out")
async def guest_leave(visit_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "guests")
    data = await svc.guest_out(db, claims["tenant_id"], visit_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Guest out")
