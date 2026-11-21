"""Routes: member portal (public, by private link), trainer portal, and the staff side of both."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_fitness_api as fit_api
from app import gym_nutrition_api as nut_api
from app import gym_fitness, gym_nutrition
from app import gym_facilities as fac_svc
from app import gym_facilities_api as fac_api
from app import gym_portal as svc
from app.db import get_db
from app.schemas import UuidIdValue
from app.security import require_permission

router = APIRouter(prefix="/gym", tags=["gym"])
member_router = APIRouter(prefix="/public/gym-member", tags=["gym-member-portal"])


def _env(data, message: str = "OK"):
    from app.api import env

    return env(data, message)


class LinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: Annotated[int, Field(ge=1, le=svc.LINK_DAYS)] = svc.LINK_DAYS


class BookBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    waitlist: bool = False


class FeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["complaint", "feedback", "rating"]
    rating: Annotated[int, Field(ge=1, le=5)] | None = None
    message: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    trainer_id: UuidIdValue | None = None


class ConsentBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: bool


class ResolveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution: Annotated[str, Field(min_length=3, max_length=500)]


class TrainerLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UuidIdValue | None = None


class SessionStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["completed", "cancelled", "no_show"]


Read = Depends(require_permission("gym", "read"))
Write = Depends(require_permission("gym", "write"))


# --- Staff side -----------------------------------------------------------------------------


@router.post("/members/{member_id}/portal-link")
async def portal_link(member_id: UuidIdValue, payload: LinkBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.issue_link(db, claims["tenant_id"], member_id, days=payload.days, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Shown once. Send it to the member.")


@router.post("/members/{member_id}/portal-link/revoke")
async def portal_revoke(member_id: UuidIdValue, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "members")
    data = await svc.revoke_links(db, claims["tenant_id"], member_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Link cancelled")


@router.get("/feedback")
async def feedback(status: Literal["open", "closed"] | None = None, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.list_feedback(db, claims["tenant_id"], status=status))


@router.post("/feedback/{feedback_id}/close")
async def feedback_close(feedback_id: UuidIdValue, payload: ResolveBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    data = await svc.resolve_feedback(db, claims["tenant_id"], feedback_id, resolution=payload.resolution, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Closed")


@router.get("/reports/trainer-ratings")
async def ratings(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "correct")
    return _env(await svc.trainer_ratings(db, claims["tenant_id"]))


@router.post("/trainers/{trainer_id}/link-user")
async def trainer_link(trainer_id: UuidIdValue, payload: TrainerLink, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "people")
    data = await svc.link_trainer(db, claims["tenant_id"], trainer_id, payload.user_id, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


# --- Trainer portal (signed in) -------------------------------------------------------------


@router.get("/trainer-portal/me")
async def tp_me(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    return _env(await svc.trainer_overview(db, claims["tenant_id"], t))


@router.get("/trainer-portal/sessions")
async def tp_sessions(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    return _env(await svc.trainer_sessions(db, claims["tenant_id"], t))


@router.post("/trainer-portal/sessions/{session_id}")
async def tp_session_set(session_id: UuidIdValue, payload: SessionStatus, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    data = await svc.trainer_set_session(db, claims["tenant_id"], t, session_id, status=payload.status, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Saved")


@router.get("/trainer-portal/members")
async def tp_members(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "training")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    return _env(await svc.trainer_members(db, claims["tenant_id"], t))


@router.get("/trainer-portal/programmes")
async def tp_programmes(claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "fitness")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    return _env(await svc.trainer_programmes(db, claims["tenant_id"], t))


@router.get("/trainer-portal/members/{member_id}/measurements")
async def tp_measurements(member_id: UuidIdValue, claims=Read, db: AsyncSession = Depends(get_db)):
    base.job(claims, "fitness")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    await svc.require_assigned(db, claims["tenant_id"], t, member_id)
    return _env(await gym_fitness.list_measurements(db, claims["tenant_id"], member_id))


@router.post("/trainer-portal/members/{member_id}/measurements")
async def tp_measure_add(member_id: UuidIdValue, payload: fit_api.MeasurementBody, claims=Write, db: AsyncSession = Depends(get_db)):
    base.job(claims, "fitness")
    t = await svc.my_trainer(db, claims["tenant_id"], claims)
    await svc.require_assigned(db, claims["tenant_id"], t, member_id)
    data = await gym_fitness.record_measurement(db, claims["tenant_id"], member_id, payload, user_id=claims.get("sub"))
    await db.commit()
    return _env(data, "Measurements saved")


# --- Member portal (public, by private link) ------------------------------------------------


async def _who(x_portal_token: str | None = Header(default=None), db: AsyncSession = Depends(get_db)):
    tenant_id, member = await svc.member_from_token(db, x_portal_token)
    return tenant_id, member


@member_router.get("/me")
async def mp_me(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.my_overview(db, *who)
    await db.commit()
    return _env(data)


@member_router.get("/classes")
async def mp_classes(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await svc.my_classes(db, *who))


@member_router.post("/classes/{class_id}/book")
async def mp_book(class_id: UuidIdValue, payload: BookBody, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.book(db, who[0], who[1], class_id, waitlist=payload.waitlist)
    await db.commit()
    return _env(data, "Booked")


@member_router.post("/bookings/{booking_id}/cancel")
async def mp_cancel(booking_id: UuidIdValue, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.cancel_booking(db, who[0], who[1], booking_id)
    await db.commit()
    return _env(data, "Cancelled")


@member_router.get("/facilities")
async def mp_facilities(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await fac_svc.list_facilities(db, who[0], active_only=True))


@member_router.get("/facility-bookings")
async def mp_facility_bookings(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await fac_svc.list_bookings(db, who[0], member_id=who[1].id))


@member_router.post("/facilities/{facility_id}/book")
async def mp_facility_book(facility_id: UuidIdValue, payload: fac_api.PortalBookBody, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await fac_svc.book(db, who[0], facility_id, member_id=who[1].id, starts_at=payload.starts_at, minutes=payload.minutes, user_id=None)
    await db.commit()
    return _env(data, "Booked")


@member_router.post("/facility-bookings/{booking_id}/cancel")
async def mp_facility_cancel(booking_id: UuidIdValue, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await fac_svc.set_booking(db, who[0], booking_id, status="cancelled", user_id=None, member_id=who[1].id)
    await db.commit()
    return _env(data, "Cancelled")


@member_router.get("/payments")
async def mp_payments(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await svc.my_payments(db, *who))


@member_router.get("/programmes")
async def mp_programmes(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await svc.my_programmes(db, *who))


@member_router.post("/programmes/{programme_id}/workouts")
async def mp_workout(programme_id: UuidIdValue, payload: fit_api.WorkoutBody, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.log_my_workout(db, who[0], who[1], programme_id, payload)
    await db.commit()
    return _env(data, "Workout logged")


@member_router.get("/measurements")
async def mp_measurements(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await gym_fitness.list_measurements(db, who[0], who[1].id))


@member_router.get("/nutrition")
async def mp_nutrition(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    return _env(await svc.my_nutrition(db, *who))


@member_router.post("/nutrition-plans/{plan_id}/intake")
async def mp_intake(plan_id: UuidIdValue, payload: nut_api.IntakeBody, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.log_my_intake(db, who[0], who[1], plan_id, payload)
    await db.commit()
    return _env(data, "Intake logged")


@member_router.post("/door-code")
async def mp_door_code(who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.my_door_code(db, *who)
    await db.commit()
    return _env(data, "Show this at the door")


@member_router.post("/feedback")
async def mp_feedback(payload: FeedbackBody, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.send_feedback(db, who[0], who[1], payload)
    await db.commit()
    return _env(data, "Thank you. The gym has your message.")


@member_router.post("/consent")
async def mp_consent(payload: ConsentBody, who=Depends(_who), db: AsyncSession = Depends(get_db)):
    data = await svc.set_my_consent(db, who[0], who[1], consent=payload.consent)
    await db.commit()
    return _env(data, "Saved")
