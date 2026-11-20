"""Routes for gym leads, consent and campaigns. Leads: front desk and managers. Campaigns: managers."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_crm as svc
from app.db import get_db
from app.schemas import E164PhoneValue, PartyNameValue, UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])
Notes = Annotated[str, Field(min_length=1, max_length=1000)]


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class LeadBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: PartyNameValue
    phone: E164PhoneValue | None = None
    email: EmailStr | None = None
    source: Literal["walk_in", "referral", "social", "website", "event", "phone", "other"] = "walk_in"
    next_follow_up: date | None = None
    notes: Notes | None = None
    marketing_consent: bool = False
    referred_by_member_id: UuidIdValue | None = None


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["contacted", "trial", "lost"] | None = None
    trial_days: Annotated[int, Field(ge=1, le=30)] | None = None
    next_follow_up: date | None = None
    notes: Notes | None = None


class ConsentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool


class CampaignBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, Field(min_length=1, max_length=150)]
    channel: Literal["sms", "email"]
    audience: Literal["active", "expiring", "lapsed", "leads"]
    kind: Literal["marketing", "service"] = "marketing"
    subject: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    message: Annotated[str, Field(min_length=1, max_length=1000)]


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


@router.get("/leads")
async def leads(status: Literal["new", "contacted", "trial", "converted", "lost"] | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    return _env(await svc.list_leads(db, claims["tenant_id"], status=status))


@router.get("/leads/follow-ups")
async def follow_ups(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    return _env(await svc.follow_ups_due(db, claims["tenant_id"]))


@router.post("/leads")
async def lead_add(payload: LeadBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    row = await svc.create_lead(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(svc.present_lead(row), "Lead added")


@router.post("/leads/{lead_id}")
async def lead_update(lead_id: UuidIdValue, payload: LeadUpdate, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.update_lead(db, claims["tenant_id"], lead_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/leads/{lead_id}/convert")
async def lead_convert(lead_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.convert_lead(db, claims["tenant_id"], lead_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Now a member. Sell their first plan at the till.")


@router.get("/reports/leads")
async def lead_report(start_date: date | None = None, end_date: date | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    end = end_date or date.today()
    return _env(await svc.lead_report(db, claims["tenant_id"], start=start_date or end - timedelta(days=89), end=end))


@router.post("/members/{member_id}/consent")
async def consent(member_id: UuidIdValue, payload: ConsentBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.set_member_consent(db, claims["tenant_id"], member_id, consent=payload.consent, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/campaigns")
async def campaigns(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.list_campaigns(db, claims["tenant_id"]))


@router.post("/campaigns")
async def campaign_add(payload: CampaignBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.create_campaign(db, claims["tenant_id"], payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Campaign saved as a draft")


@router.post("/campaigns/{campaign_id}/send")
async def campaign_send(campaign_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.send_campaign(db, claims["tenant_id"], campaign_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Campaign sent")


@router.post("/campaigns/{campaign_id}/retry")
async def campaign_retry(campaign_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.retry_failed(db, claims["tenant_id"], campaign_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Retried")


class ReminderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Literal["sms", "email"]


class AutoReminderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channels: Literal["", "sms", "email", "both"]


@router.get("/reminders/auto")
async def reminders_auto(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env({"reminder_channels": await svc.reminder_setting(db, claims["tenant_id"])})


@router.post("/reminders/auto")
async def reminders_auto_set(payload: AutoReminderBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.set_reminder_setting(db, claims["tenant_id"], payload.channels, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.post("/reminders/run")
async def reminders_run(payload: ReminderBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.run_renewal_reminders(db, claims["tenant_id"], channel=payload.channel, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Reminders sent")


@router.get("/campaigns/{campaign_id}/recipients")
async def campaign_recipients(campaign_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.campaign_recipients(db, claims["tenant_id"], campaign_id))
