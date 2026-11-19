"""Routes for RFID card attendance (see hrm_rfid).

`router` is for HR (signed in). `reader_router` is for the card reader itself: no login, only
its own token in the `X-Reader-Token` header.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import hrm as svc
from app import hrm_rfid as rfid
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/hrm/rfid", tags=["hrm"])
reader_router = APIRouter(prefix="/hrm/rfid", tags=["hrm"])
Read = Depends(require_permission("hrm", "read"))
Write = Depends(require_permission("hrm", "write"))


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class ReaderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=2, max_length=120)]
    site_id: UuidIdValue | None = None


class CardBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: UuidIdValue
    card_uid: Annotated[str, Field(min_length=4, max_length=48)]


class TapBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_uid: Annotated[str, Field(min_length=4, max_length=48)]
    ref: Annotated[str, Field(min_length=1, max_length=60)]
    at: datetime | None = None


@router.get("/readers")
async def readers(claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env([rfid.serialize_reader(r) for r in await rfid.readers(db, claims["tenant_id"])])


@router.post("/readers")
async def add_reader(body: ReaderBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")  # a reader feeds pay, like the biometric link
    row, token = await rfid.add_reader(db, claims["tenant_id"], name=body.name, site_id=body.site_id, user_id=claims.get("sub"))
    await db.commit()
    return _env({**rfid.serialize_reader(row), "token": token}, "Reader added. Copy the token now: it is not shown again.")


@router.post("/readers/{reader_id}/off")
async def reader_off(reader_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "payroll")
    row = await rfid.switch_off(db, claims["tenant_id"], reader_id, claims.get("sub"))
    await db.commit()
    return _env(rfid.serialize_reader(row), "Switched off")


@router.get("/cards")
async def cards(claims=Read, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    return _env(await rfid.cards(db, claims["tenant_id"]))


@router.post("/cards")
async def issue_card(body: CardBody, claims=Write, db: AsyncSession = Depends(get_db)):
    svc.job(claims, "attendance")
    out = await rfid.assign_card(db, claims["tenant_id"], body.employee_id, body.card_uid, claims.get("sub"))
    await db.commit()
    return _env(out, "Card issued")


@reader_router.post("/punch")
async def tap(body: TapBody, x_reader_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    reader = await rfid.reader_for_token(db, x_reader_token)
    out = await rfid.punch(db, reader, card_uid=body.card_uid, ref=body.ref, at=body.at)
    await db.commit()
    return _env(out)
