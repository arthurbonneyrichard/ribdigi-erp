"""Routes for the gym door: credentials, scans, devices, offline sync."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_door as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class CredentialBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member_id: UuidIdValue
    kind: Literal["qr", "card", "rfid", "nfc", "barcode"] = "qr"
    token: Annotated[str, Field(min_length=4, max_length=120)] | None = None  # a card that has its own number
    label: Annotated[str, Field(min_length=1, max_length=80)] | None = None


class ScanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: Annotated[str, Field(min_length=4, max_length=200)]
    branch_id: UuidIdValue | None = None


class DeviceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=120)]
    kind: Literal["qr_scanner", "barcode_scanner", "rfid_reader", "nfc_reader", "fingerprint", "face", "turnstile"] = "qr_scanner"
    branch_id: UuidIdValue | None = None


class VerifiedBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verified: bool


class EventBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: Annotated[str, Field(min_length=8, max_length=64)]
    token: Annotated[str, Field(min_length=4, max_length=200)]
    occurred_at: datetime
    branch_id: UuidIdValue | None = None


class SyncBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_id: UuidIdValue | None = None
    events: Annotated[list[EventBody], Field(min_length=1, max_length=svc.MAX_BATCH)]


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.post("/credentials")
async def credential_issue(payload: CredentialBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.issue_credential(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Shown once. Give it to the member now.")


@router.get("/members/{member_id}/credentials")
async def credentials(member_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    return _env(await svc.list_credentials(db, claims["tenant_id"], member_id))


@router.post("/credentials/{credential_id}/revoke")
async def credential_revoke(credential_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.revoke_credential(db, claims["tenant_id"], credential_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Cancelled")


@router.post("/check-ins/scan")
async def scan(payload: ScanBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "door")
    data = await svc.scan(db, claims["tenant_id"], token=payload.token, branch_id=payload.branch_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, data["message"])


@router.get("/devices")
async def devices(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.list_devices(db, claims["tenant_id"]))


@router.post("/devices")
async def device_add(payload: DeviceBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.register_device(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Device added")


@router.post("/devices/{device_id}/verified")
async def device_verified(device_id: UuidIdValue, payload: VerifiedBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.mark_device_verified(db, claims["tenant_id"], device_id, verified=payload.verified, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/door/roster")
async def roster(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "door")
    return _env(await svc.roster(db, claims["tenant_id"]))


@router.post("/door/sync")
async def sync(payload: SyncBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "door")
    data = await svc.sync_events(db, claims["tenant_id"], device_id=payload.device_id, events=payload.events, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Synced")


@router.get("/door/attention")
async def attention(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.attention_list(db, claims["tenant_id"]))


@router.post("/door/attention/{event_row_id}/reviewed")
async def attention_clear(event_row_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.clear_attention(db, claims["tenant_id"], event_row_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Reviewed")
