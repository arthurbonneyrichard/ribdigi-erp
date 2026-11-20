"""Gym member portal and trainer portal.

Member portal: a member opens a private link staff gave them. The link carries a random token;
only its hash is stored, it expires (30 days at most) and can be cancelled. The member id always
comes from the token, never from the request, so a member can only ever see or change their own
records. They can see their plan, book and cancel classes, see their programmes, measurements and
nutrition plan, log their own workouts and intake, see their payments, send feedback, and show a
door code.

What a member cannot do here: renew by paying. Ribdigi records payments but does not take them,
and an unverified payment reference is not proof of payment, so renewals stay at the till.

Trainer portal: a trainer sees only their own sessions, their own programmes, and the members they
are assigned to (through a session or a programme), once staff link the trainer to a login.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import gym_commissions, gym_door, gym_fitness, gym_nutrition, gym_ops
from app import models as m
from app.gym import _audit, _member
from app.honesty import optional_honest_narrative

LINK_DAYS = 30


def _hash(token: str) -> str:
    return hashlib.sha256(str(token or "").strip().encode()).hexdigest()


# --- Staff side: links ----------------------------------------------------------------------


async def issue_link(db: AsyncSession, tenant_id: str, member_id: str, *, days: int, user_id) -> dict:
    member = await _member(db, tenant_id, member_id)
    days = max(1, min(int(days or LINK_DAYS), LINK_DAYS))
    old = (
        await db.execute(select(m.GymPortalLink).where(m.GymPortalLink.member_id == member.id, m.GymPortalLink.status == "active").with_for_update())
    ).scalars().all()
    for row in old:  # one live link per member: a new one cancels the last
        row.status = "revoked"
    token = "gmp_" + secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(days=days)
    db.add(m.GymPortalLink(tenant_id=tenant_id, member_id=member.id, token_hash=_hash(token), expires_at=expires, created_by=user_id))
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_portal_link_issued", "gym_member", member.id, {"days": days})
    return {"member_id": member.id, "token": token, "expires_at": expires.isoformat()}


async def revoke_links(db: AsyncSession, tenant_id: str, member_id: str, *, user_id) -> dict:
    member = await _member(db, tenant_id, member_id)
    rows = (await db.execute(select(m.GymPortalLink).where(m.GymPortalLink.member_id == member.id, m.GymPortalLink.status == "active"))).scalars().all()
    for row in rows:
        row.status = "revoked"
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_portal_link_revoked", "gym_member", member.id, {"count": len(rows)})
    return {"revoked": len(rows)}


# --- Member side ----------------------------------------------------------------------------


async def member_from_token(db: AsyncSession, token: str | None) -> tuple[str, m.GymMember]:
    """Resolve a portal token to (tenant_id, member). Any problem is the same plain 401."""
    bad = HTTPException(status_code=401, detail="This link is not valid. Ask the gym for a new one.")
    if not token or len(token) > 200:
        raise bad
    link = (await db.execute(select(m.GymPortalLink).where(m.GymPortalLink.token_hash == _hash(token)))).scalar_one_or_none()
    if link is None or link.status != "active" or link.expires_at < datetime.utcnow():
        raise bad
    tenant = await db.get(m.Tenant, link.tenant_id)
    if tenant is None or tenant.industry != "gym" or str(getattr(tenant, "status", "") or "").lower() == "suspended":
        raise bad
    member = await db.get(m.GymMember, link.member_id)
    if member is None or member.tenant_id != link.tenant_id:
        raise bad
    link.last_used_at = datetime.utcnow()
    return link.tenant_id, member


async def my_overview(db: AsyncSession, tenant_id: str, member: m.GymMember) -> dict:
    full = await base.present_member(db, member)
    keep = ("id", "member_number", "full_name", "joined_on", "state", "plan_name", "ends_on", "days_left", "visits_left")  # never the staff notes
    out = {k: full[k] for k in keep if k in full}
    out["phone"], out["email"], out["marketing_consent"] = member.phone, member.email, bool(member.marketing_consent)
    return out


async def my_classes(db: AsyncSession, tenant_id: str, member: m.GymMember) -> list[dict]:
    """Upcoming classes. Other members' names are never shown."""
    out = []
    for row in await base.list_classes(db, tenant_id):
        bookings = (await db.execute(select(m.GymClassBooking).where(m.GymClassBooking.class_id == row.id, m.GymClassBooking.status != "cancelled"))).scalars().all()
        mine = next((b for b in bookings if b.member_id == member.id), None)
        taken = len([b for b in bookings if b.status != "waitlisted"])
        out.append(
            {
                "id": row.id, "name": row.name, "trainer_name": row.trainer_name, "starts_at": row.starts_at.isoformat(),
                "places_left": max(0, int(row.capacity) - taken), "my_booking_id": mine.id if mine else None, "my_status": mine.status if mine else None,
            }
        )
    return out


async def book(db: AsyncSession, tenant_id: str, member: m.GymMember, class_id: str, *, waitlist: bool) -> list[dict]:
    await base.book_class(db, tenant_id, class_id, member_id=member.id, user_id=None, waitlist=waitlist)
    await _audit(db, tenant_id, None, "gym_portal_class_booked", "gym_member", member.id, {"class_id": class_id})
    return await my_classes(db, tenant_id, member)


async def cancel_booking(db: AsyncSession, tenant_id: str, member: m.GymMember, booking_id: str) -> list[dict]:
    row = await db.get(m.GymClassBooking, booking_id)
    if row is None or row.tenant_id != tenant_id or row.member_id != member.id:
        raise HTTPException(status_code=404, detail="Booking not found")  # someone else's booking looks the same as none
    if row.status in ("cancelled", "attended", "no_show"):
        raise HTTPException(status_code=409, detail=f"This booking is already {row.status.replace('_', ' ')}")
    await base.set_booking(db, tenant_id, booking_id, status="cancelled")
    await _audit(db, tenant_id, None, "gym_portal_class_cancelled", "gym_member", member.id, {"booking_id": booking_id})
    return await my_classes(db, tenant_id, member)


async def my_payments(db: AsyncSession, tenant_id: str, member: m.GymMember) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymPayment).where(m.GymPayment.tenant_id == tenant_id, m.GymPayment.member_id == member.id).order_by(m.GymPayment.created_at.desc()).limit(100)
        )
    ).scalars().all()
    return [{"id": r.id, "kind": r.kind, "method": r.method, "amount": base._money(r.amount), "date": r.created_at.isoformat()} for r in rows]


async def my_programmes(db: AsyncSession, tenant_id: str, member: m.GymMember) -> list[dict]:
    return await gym_fitness.list_programmes(db, tenant_id, member_id=member.id)


async def log_my_workout(db: AsyncSession, tenant_id: str, member: m.GymMember, programme_id: str, payload) -> dict:
    prog = await db.get(m.GymProgramme, programme_id)
    if prog is None or prog.tenant_id != tenant_id or prog.member_id != member.id:
        raise HTTPException(status_code=404, detail="Programme not found")
    return await gym_fitness.log_workout(db, tenant_id, programme_id, payload, user_id=None)


async def my_nutrition(db: AsyncSession, tenant_id: str, member: m.GymMember) -> list[dict]:
    return await gym_nutrition.list_plans(db, tenant_id, member_id=member.id)


async def log_my_intake(db: AsyncSession, tenant_id: str, member: m.GymMember, plan_id: str, payload) -> dict:
    plan = await db.get(m.GymNutritionPlan, plan_id)
    if plan is None or plan.tenant_id != tenant_id or plan.member_id != member.id:
        raise HTTPException(status_code=404, detail="Nutrition plan not found")
    return await gym_nutrition.log_intake(db, tenant_id, plan_id, payload, user_id=None)


async def my_door_code(db: AsyncSession, tenant_id: str, member: m.GymMember) -> dict:
    """A fresh door QR. The last portal-issued one stops working."""
    old = (
        await db.execute(
            select(m.GymCredential).where(m.GymCredential.member_id == member.id, m.GymCredential.label == "portal", m.GymCredential.status == "active")
        )
    ).scalars().all()
    for row in old:
        row.status, row.revoked_at = "revoked", datetime.utcnow()
    token = "gym_" + secrets.token_urlsafe(24)
    db.add(m.GymCredential(tenant_id=tenant_id, member_id=member.id, kind="qr", label="portal", token_hash=gym_door.hash_token(token)))
    await db.flush()
    return {"token": token, "qr_png": gym_door.qr_image(token)}


async def send_feedback(db: AsyncSession, tenant_id: str, member: m.GymMember, payload) -> dict:
    if payload.kind == "rating" and payload.rating is None:
        raise HTTPException(status_code=422, detail="Choose a rating from 1 to 5")
    if payload.kind != "rating" and not payload.message:
        raise HTTPException(status_code=422, detail="Write a few words")
    if payload.trainer_id:
        tr = await db.get(m.GymTrainer, payload.trainer_id)
        if tr is None or tr.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Trainer not found")
    row = m.GymFeedback(
        tenant_id=tenant_id, member_id=member.id, trainer_id=payload.trainer_id, kind=payload.kind,
        rating=payload.rating if payload.kind == "rating" else None,
        message=optional_honest_narrative(payload.message, label="message", max_length=1000),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, None, "gym_feedback_sent", "gym_member", member.id, {"kind": payload.kind})
    return {"id": row.id, "status": row.status}


async def set_my_consent(db: AsyncSession, tenant_id: str, member: m.GymMember, *, consent: bool) -> dict:
    member.marketing_consent = consent
    member.consent_at = datetime.utcnow() if consent else None
    await db.flush()
    await _audit(db, tenant_id, None, "gym_consent_set" if consent else "gym_consent_withdrawn", "gym_member", member.id, {"by": "member"})
    return {"marketing_consent": consent}


# --- Staff side: feedback -------------------------------------------------------------------


async def list_feedback(db: AsyncSession, tenant_id: str, *, status: str | None = None) -> list[dict]:
    stmt = select(m.GymFeedback, m.GymMember.full_name).join(m.GymMember, m.GymMember.id == m.GymFeedback.member_id).where(m.GymFeedback.tenant_id == tenant_id).order_by(m.GymFeedback.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(m.GymFeedback.status == status)
    return [
        {"id": r.id, "member_name": name, "kind": r.kind, "rating": r.rating, "message": r.message, "status": r.status, "trainer_id": r.trainer_id, "resolution": r.resolution, "date": r.created_at.isoformat()}
        for r, name in (await db.execute(stmt)).all()
    ]


async def resolve_feedback(db: AsyncSession, tenant_id: str, feedback_id: str, *, resolution: str, user_id) -> dict:
    row = await db.get(m.GymFeedback, feedback_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Feedback not found")
    if row.status == "closed":
        raise HTTPException(status_code=409, detail="Already closed")
    row.status, row.resolution = "closed", optional_honest_narrative(resolution, label="resolution", max_length=500)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_feedback_closed", "gym_feedback", row.id, {})
    return {"id": row.id, "status": row.status}


async def trainer_ratings(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymTrainer.id, m.GymTrainer.full_name, func.avg(m.GymFeedback.rating), func.count(m.GymFeedback.id))
            .join(m.GymFeedback, m.GymFeedback.trainer_id == m.GymTrainer.id)
            .where(m.GymTrainer.tenant_id == tenant_id, m.GymFeedback.kind == "rating")
            .group_by(m.GymTrainer.id, m.GymTrainer.full_name)
        )
    ).all()
    return [{"trainer_id": i, "trainer": n, "average": round(float(a), 2), "ratings": int(c)} for i, n, a, c in rows]


# --- Trainer portal -------------------------------------------------------------------------


async def link_trainer(db: AsyncSession, tenant_id: str, trainer_id: str, user_id_to_link: str | None, *, user_id) -> dict:
    trainer = await db.get(m.GymTrainer, trainer_id)
    if trainer is None or trainer.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Trainer not found")
    if user_id_to_link:
        user = await db.get(m.User, user_id_to_link)
        if user is None or user.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="User not found")
        taken = (await db.execute(select(m.GymTrainer.id).where(m.GymTrainer.user_id == user_id_to_link, m.GymTrainer.id != trainer.id))).first()
        if taken:
            raise HTTPException(status_code=409, detail="That login is already linked to another trainer")
    trainer.user_id = user_id_to_link
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_trainer_linked", "gym_trainer", trainer.id, {"user_id": user_id_to_link})
    return {"trainer_id": trainer.id, "user_id": trainer.user_id}


async def my_trainer(db: AsyncSession, tenant_id: str, claims: dict) -> m.GymTrainer:
    row = (await db.execute(select(m.GymTrainer).where(m.GymTrainer.tenant_id == tenant_id, m.GymTrainer.user_id == claims.get("sub")))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Your login is not linked to a trainer profile. Ask a manager.")
    return row


async def _assigned_ids(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer) -> set[str]:
    a = (await db.execute(select(m.GymTrainingSession.member_id).where(m.GymTrainingSession.tenant_id == tenant_id, m.GymTrainingSession.trainer_id == trainer.id))).scalars().all()
    b = (await db.execute(select(m.GymProgramme.member_id).where(m.GymProgramme.tenant_id == tenant_id, m.GymProgramme.trainer_id == trainer.id, m.GymProgramme.status == "active"))).scalars().all()
    return set(a) | set(b)


async def trainer_overview(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer) -> dict:
    rating = (
        await db.execute(select(func.avg(m.GymFeedback.rating), func.count(m.GymFeedback.id)).where(m.GymFeedback.trainer_id == trainer.id, m.GymFeedback.kind == "rating"))
    ).one()
    today = datetime.combine(date.today(), time.min)
    upcoming = (
        await db.execute(
            select(func.count()).select_from(m.GymTrainingSession).where(m.GymTrainingSession.trainer_id == trainer.id, m.GymTrainingSession.status == "booked", m.GymTrainingSession.starts_at >= today)
        )
    ).scalar_one()
    return {
        "trainer": gym_ops.present_trainer(trainer), "members": len(await _assigned_ids(db, tenant_id, trainer)), "upcoming_sessions": int(upcoming or 0),
        "average_rating": round(float(rating[0]), 2) if rating[0] is not None else None, "ratings": int(rating[1] or 0),
        "commission_accrued": await gym_commissions.accrued_for_trainer(db, tenant_id, trainer.id),
    }


async def trainer_sessions(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymTrainingSession, m.GymMember)
            .join(m.GymMember, m.GymMember.id == m.GymTrainingSession.member_id)
            .where(m.GymTrainingSession.tenant_id == tenant_id, m.GymTrainingSession.trainer_id == trainer.id, m.GymTrainingSession.starts_at >= datetime.utcnow() - timedelta(days=14))
            .order_by(m.GymTrainingSession.starts_at)
        )
    ).all()
    return [gym_ops.present_session(s, trainer, mem) for s, mem in rows]


async def trainer_set_session(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer, session_id: str, *, status: str, user_id) -> dict:
    row = await db.get(m.GymTrainingSession, session_id)
    if row is None or row.tenant_id != tenant_id or row.trainer_id != trainer.id:
        raise HTTPException(status_code=404, detail="Session not found")
    return await gym_ops.set_session(db, tenant_id, session_id, status=status, user_id=user_id)


async def trainer_members(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer) -> list[dict]:
    out = []
    for mid in sorted(await _assigned_ids(db, tenant_id, trainer)):
        mem = await db.get(m.GymMember, mid)
        if mem is not None:
            pm = await base.present_member(db, mem)
            out.append({"id": mem.id, "full_name": mem.full_name, "state": pm["state"], "plan_name": pm["plan_name"], "ends_on": pm["ends_on"]})
    return out


async def trainer_programmes(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer) -> list[dict]:
    rows = (await db.execute(select(m.GymProgramme).where(m.GymProgramme.tenant_id == tenant_id, m.GymProgramme.trainer_id == trainer.id).order_by(m.GymProgramme.created_at.desc()))).scalars().all()
    return [await gym_fitness.present_programme(db, r) for r in rows]


async def require_assigned(db: AsyncSession, tenant_id: str, trainer: m.GymTrainer, member_id: str) -> None:
    if member_id not in await _assigned_ids(db, tenant_id, trainer):
        raise HTTPException(status_code=404, detail="Member not found")  # not yours looks the same as none
