"""Routes for the till lock and for managing cashier passcodes."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import pos_lock as lock_svc
from app.db import get_db
from app.schemas import FiniteMoneyValue, UuidIdValue
from app.security import current_claims, require_permission

router = APIRouter(tags=["pos-lock"])

Surface = Literal["retail", "restaurant"]
DeviceId = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")]
PasscodeDigits = Annotated[str, Field(min_length=lock_svc.PASSCODE_LENGTH, max_length=lock_svc.PASSCODE_LENGTH, pattern=r"^\d+$")]


def _env(data, message: str = "OK") -> dict:
    return {"success": True, "data": data, "message": message}


class TillBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    surface: Surface
    device_id: DeviceId


class UnlockBody(TillBody):
    passcode: PasscodeDigits


class LockBody(TillBody):
    reason: Literal["idle", "manual"] = "idle"


class HandoverBody(TillBody):
    from_user_id: UuidIdValue
    decision: Literal["take_over", "keep_for_owner"]
    item_count: int = Field(ge=0, le=500)
    total: FiniteMoneyValue = 0


class PasscodeSetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Omit to have a passcode generated and shown once.
    passcode: PasscodeDigits | None = None


class PasscodeActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


def _login_user(claims: dict) -> str:
    return claims.get("login_user_id") or claims["sub"]


def _reject_api_key(claims: dict) -> None:
    if claims.get("auth_method") == "api_key":
        raise HTTPException(status_code=403, detail="A till is unlocked by a person, not an API key.")


@router.get("/pos/lock/state")
async def pos_lock_state(
    surface: Surface,
    device_id: DeviceId,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    return _env(await lock_svc.till_state(db, claims=claims, device_id=device_id, surface=surface))


@router.post("/pos/lock/unlock")
async def pos_lock_unlock(
    payload: UnlockBody,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    _reject_api_key(claims)
    data = await lock_svc.unlock_with_passcode(
        db, claims=claims, login_user_id=_login_user(claims), device_id=payload.device_id,
        surface=payload.surface, passcode=payload.passcode,
    )
    return _env(data, "Till unlocked")


@router.post("/pos/lock/lock")
async def pos_lock_lock(
    payload: LockBody,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    _reject_api_key(claims)
    data = await lock_svc.lock_till(
        db, claims=claims, device_id=payload.device_id, surface=payload.surface, reason=payload.reason
    )
    return _env(data, "Till locked")


@router.post("/pos/lock/ping")
async def pos_lock_ping(
    payload: TillBody,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    return _env(await lock_svc.note_activity(db, claims=claims))


@router.post("/pos/lock/handover")
async def pos_lock_handover(
    payload: HandoverBody,
    claims=Depends(current_claims),
    db: AsyncSession = Depends(get_db),
):
    data = await lock_svc.record_handover(
        db, claims=claims, device_id=payload.device_id, surface=payload.surface,
        from_user_id=payload.from_user_id, decision=payload.decision,
        item_count=payload.item_count, total=float(payload.total or 0),
    )
    return _env(data, "Recorded")


@router.get("/users/pos-passcodes")
async def pos_passcode_list(
    claims=Depends(require_permission("users", "read")),
    db: AsyncSession = Depends(get_db),
):
    return _env(await lock_svc.list_passcodes(db, claims["tenant_id"]))


@router.put("/users/{user_id}/pos-passcode")
async def pos_passcode_set(
    user_id: UuidIdValue,
    payload: PasscodeSetBody,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = await lock_svc.set_passcode(
        db, tenant_id=claims["tenant_id"], admin_id=claims["sub"], user_id=user_id, passcode=payload.passcode
    )
    return _env(data, "Passcode saved")


@router.patch("/users/{user_id}/pos-passcode")
async def pos_passcode_active(
    user_id: UuidIdValue,
    payload: PasscodeActiveBody,
    claims=Depends(require_permission("users", "write")),
    db: AsyncSession = Depends(get_db),
):
    data = await lock_svc.set_passcode_active(
        db, tenant_id=claims["tenant_id"], admin_id=claims["sub"], user_id=user_id, is_active=payload.is_active
    )
    return _env(data, "Passcode activated" if payload.is_active else "Passcode deactivated")
