"""Settings for order and booking alerts, shared by the restaurant, the online shop and the hotel."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import online_alerts as core
from app.db import get_db
from app.schemas import E164PhoneValue
from app.security import require_roles

router = APIRouter(prefix="/online-alerts", tags=["online-alerts"])

can_manage = require_roles("company_admin", "super_admin", "restaurant_manager", "hotel_manager", "store_manager")


def _env(data, message: str = "OK") -> dict:
    return {"success": True, "data": data, "message": message}


class AlertsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    emails: list[EmailStr] | None = Field(default=None, max_length=5)
    whatsapp: E164PhoneValue | None = None
    whatsapp_from: E164PhoneValue | None = None
    whatsapp_template: Annotated[str, Field(max_length=40)] | None = None
    orders: bool | None = None
    bookings: bool | None = None
    email_on: bool | None = None
    whatsapp_on: bool | None = None


async def _tenant(db: AsyncSession, claims):
    from app import tenants as tenants_svc

    return await tenants_svc.get_tenant(db, claims["tenant_id"])


@router.get("/favicon")
async def favicon_get(request: Request, claims=Depends(can_manage), db: AsyncSession = Depends(get_db)):
    from app import site_favicon

    tenant = await _tenant(db, claims)
    if not site_favicon.key_of(tenant):
        return Response(status_code=404)
    return site_favicon.image_response(tenant, request, public=False)


@router.post("/favicon")
async def favicon_upload(
    file: UploadFile = File(...), claims=Depends(can_manage), db: AsyncSession = Depends(get_db)
):
    from app import site_favicon

    data = await site_favicon.save(db, await _tenant(db, claims), file, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Icon saved")


@router.delete("/favicon")
async def favicon_delete(claims=Depends(can_manage), db: AsyncSession = Depends(get_db)):
    from app import site_favicon

    data = await site_favicon.remove(db, await _tenant(db, claims), user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Icon removed")


@router.get("")
async def alerts_get(claims=Depends(can_manage), db: AsyncSession = Depends(get_db)):
    return _env(core.serialize(await _tenant(db, claims)))


@router.put("")
async def alerts_put(payload: AlertsBody, claims=Depends(can_manage), db: AsyncSession = Depends(get_db)):
    data = await core.save_alerts(db, await _tenant(db, claims), payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Alerts saved")


@router.post("/test")
async def alerts_test(claims=Depends(can_manage), db: AsyncSession = Depends(get_db)):
    tenant = await _tenant(db, claims)
    industry = core.industry_of(tenant)
    if industry == "restaurant":
        title, lines, link = core.compose_restaurant(
            tenant, "order",
            {"number": "R-TEST", "service": "pickup", "total": 45, "name": "Test Guest", "phone": "+233200000000",
             "items": "2× Jollof, 1× Sobolo", "notes": "This is a test."},
        )
    elif industry == "hotel":
        title, lines, link = core.compose_hotel(
            tenant,
            {"number": "RES-TEST", "name": "Test Guest", "phone": "+233200000000", "check_in": "2030-01-10",
             "check_out": "2030-01-12", "nights": 2, "adults": 2, "children": 0, "room": "Room 101", "total": 600,
             "notes": "This is a test."},
        )
    else:
        title, lines, link = core.compose_retail(
            tenant,
            {"number": "W-TEST", "fulfillment": "delivery", "total": 120, "paid": False, "name": "Test Customer",
             "phone": "+233200000000", "items": "2× Sample item", "address": "12 Test Street", "notes": "This is a test."},
        )
    result = await core.deliver(tenant, "Test: " + title, lines, link)
    return _env(result, "Test sent")
