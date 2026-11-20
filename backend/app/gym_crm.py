"""Gym CRM: leads, trials, conversion to member, consent and campaigns.

Messaging rules:
- Marketing goes only to people who said yes (member or lead `marketing_consent`), and never to an
  email address on the platform's marketing suppression list. Each marketing email carries the
  signed unsubscribe link and List-Unsubscribe headers (privacy.py).
- A "service" message (a renewal reminder to members whose plan ends soon) is the only kind that
  skips consent. Nothing promotional may be sent as service: the audience is fixed to `expiring`.
- Sending uses the company's own SMS/SMTP settings. The result says which mode ran
  (smtp/twilio, console for development, or disabled). Nothing is marked sent that was not sent.
- WhatsApp has no provider wired, so it is not offered.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import emailer
from app import models as m
from app import privacy
from app import sms as sms_svc
from app.gym import _audit, _latest, _member, _state, create_member, expiring
from app.honesty import optional_honest_narrative, require_honest_narrative

SOURCES = ("walk_in", "referral", "social", "website", "event", "phone", "other")
OPEN = ("new", "contacted", "trial")
MAX_SEND = 500


def present_lead(row: m.GymLead) -> dict:
    return {
        "id": row.id, "full_name": row.full_name, "phone": row.phone, "email": row.email, "source": row.source, "status": row.status,
        "next_follow_up": row.next_follow_up.isoformat() if row.next_follow_up else None,
        "trial_ends_on": row.trial_ends_on.isoformat() if row.trial_ends_on else None,
        "notes": row.notes, "marketing_consent": bool(row.marketing_consent), "member_id": row.member_id,
        "referred_by_member_id": row.referred_by_member_id,
    }


async def _lead(db, tenant_id: str, lead_id: str, *, lock: bool = False) -> m.GymLead:
    stmt = select(m.GymLead).where(m.GymLead.id == lead_id, m.GymLead.tenant_id == tenant_id)
    if lock:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return row


async def create_lead(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.GymLead:
    if not (payload.phone or payload.email):
        raise HTTPException(status_code=422, detail="A lead needs a phone number or an email")
    if payload.phone:
        clash = (
            await db.execute(
                select(m.GymLead.id).where(m.GymLead.tenant_id == tenant_id, m.GymLead.phone == payload.phone, m.GymLead.status.in_(OPEN))
            )
        ).first()
        if clash:
            raise HTTPException(status_code=409, detail="This person is already a lead")
    if payload.referred_by_member_id:
        await _member(db, tenant_id, payload.referred_by_member_id)
    row = m.GymLead(
        tenant_id=tenant_id, full_name=payload.full_name, phone=payload.phone, email=payload.email, source=payload.source,
        next_follow_up=payload.next_follow_up, notes=optional_honest_narrative(payload.notes, label="notes", max_length=2000),
        marketing_consent=bool(payload.marketing_consent), referred_by_member_id=payload.referred_by_member_id, created_by=user_id,
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_lead_created", "gym_lead", row.id, {"source": row.source})
    return row


async def list_leads(db: AsyncSession, tenant_id: str, *, status: str | None = None) -> list[dict]:
    stmt = select(m.GymLead).where(m.GymLead.tenant_id == tenant_id).order_by(m.GymLead.created_at.desc()).limit(500)
    if status:
        stmt = stmt.where(m.GymLead.status == status)
    return [present_lead(r) for r in (await db.execute(stmt)).scalars().all()]


async def follow_ups_due(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymLead)
            .where(m.GymLead.tenant_id == tenant_id, m.GymLead.status.in_(OPEN), m.GymLead.next_follow_up.is_not(None), m.GymLead.next_follow_up <= date.today())
            .order_by(m.GymLead.next_follow_up)
        )
    ).scalars().all()
    return [present_lead(r) for r in rows]


async def update_lead(db: AsyncSession, tenant_id: str, lead_id: str, payload, *, user_id) -> dict:
    row = await _lead(db, tenant_id, lead_id, lock=True)
    if row.status in ("converted", "lost"):
        raise HTTPException(status_code=409, detail=f"This lead is already {row.status}")
    if payload.status:
        row.status = payload.status
        if payload.status == "trial":
            days = int(payload.trial_days or 3)
            row.trial_ends_on = date.today() + timedelta(days=days)
    if payload.next_follow_up is not None:
        row.next_follow_up = payload.next_follow_up
    if payload.notes:
        extra = optional_honest_narrative(payload.notes, label="note", max_length=1000)
        row.notes = f"{row.notes}\n{date.today().isoformat()}: {extra}".strip() if row.notes else extra
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_lead_updated", "gym_lead", row.id, {"status": row.status})
    return present_lead(row)


async def convert_lead(db: AsyncSession, tenant_id: str, lead_id: str, *, user_id) -> dict:
    """Turn a lead into a member. Selling the first plan still goes through the till."""
    row = await _lead(db, tenant_id, lead_id, lock=True)
    if row.status == "converted":
        raise HTTPException(status_code=409, detail="This lead is already a member")
    if row.status == "lost":
        raise HTTPException(status_code=409, detail="This lead was marked lost. Add them as a new lead.")

    class _P:  # the same fields a staff-entered member has
        full_name, phone, email = row.full_name, row.phone, row.email
        emergency_contact = notes = None

    member = await create_member(db, tenant_id, _P, user_id=user_id)
    member.marketing_consent, member.consent_at = bool(row.marketing_consent), (datetime.utcnow() if row.marketing_consent else None)
    row.status, row.member_id = "converted", member.id
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_lead_converted", "gym_lead", row.id, {"member_id": member.id})
    return {"lead": present_lead(row), "member_id": member.id, "member_number": member.member_number}


async def lead_report(db: AsyncSession, tenant_id: str, *, start: date, end: date) -> dict:
    lo, hi = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())
    rows = (await db.execute(select(m.GymLead).where(m.GymLead.tenant_id == tenant_id, m.GymLead.created_at.between(lo, hi)))).scalars().all()
    total = len(rows)
    by_status: dict[str, int] = {}
    by_source: dict[str, dict] = {}
    for r in rows:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        s = by_source.setdefault(r.source, {"leads": 0, "converted": 0})
        s["leads"] += 1
        s["converted"] += 1 if r.status == "converted" else 0
    won = by_status.get("converted", 0)
    trials = sum(1 for r in rows if r.trial_ends_on is not None)
    trial_won = sum(1 for r in rows if r.trial_ends_on is not None and r.status == "converted")
    return {
        "total": total, "by_status": by_status, "by_source": by_source, "converted": won,
        "conversion_rate": round(won / total * 100, 1) if total else 0.0,
        "trials": trials, "trial_conversion_rate": round(trial_won / trials * 100, 1) if trials else 0.0,
    }


async def set_member_consent(db: AsyncSession, tenant_id: str, member_id: str, *, consent: bool, user_id) -> dict:
    member = await _member(db, tenant_id, member_id)
    member.marketing_consent = consent
    member.consent_at = datetime.utcnow() if consent else None
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_consent_set" if consent else "gym_consent_withdrawn", "gym_member", member.id, {})
    return {"member_id": member.id, "marketing_consent": consent}


# --- Campaigns ------------------------------------------------------------------------------


def present_campaign(row: m.GymCampaign, counts: dict | None = None) -> dict:
    return {
        "id": row.id, "name": row.name, "channel": row.channel, "audience": row.audience, "kind": row.kind, "subject": row.subject,
        "message": row.message, "status": row.status, "sent_at": row.sent_at.isoformat() if row.sent_at else None, "counts": counts or {},
    }


async def _counts(db, campaign_id: str) -> dict:
    rows = (await db.execute(select(m.GymCampaignRecipient.status, func.count()).where(m.GymCampaignRecipient.campaign_id == campaign_id).group_by(m.GymCampaignRecipient.status))).all()
    return {k: int(n) for k, n in rows}


async def create_campaign(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    if payload.kind == "service" and payload.audience != "expiring":
        raise HTTPException(status_code=422, detail="Only renewal reminders to members whose plan ends soon can be sent without consent")
    if payload.channel == "email" and not payload.subject:
        raise HTTPException(status_code=422, detail="An email needs a subject")
    row = m.GymCampaign(
        tenant_id=tenant_id, channel=payload.channel, audience=payload.audience, kind=payload.kind, created_by=user_id,
        name=require_honest_narrative(payload.name, label="campaign name", max_length=150),
        subject=optional_honest_narrative(payload.subject, label="subject", max_length=200),
        message=require_honest_narrative(payload.message, label="message", max_length=1000),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_campaign_created", "gym_campaign", row.id, {"audience": row.audience})
    return present_campaign(row)


async def list_campaigns(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (await db.execute(select(m.GymCampaign).where(m.GymCampaign.tenant_id == tenant_id).order_by(m.GymCampaign.created_at.desc()).limit(100))).scalars().all()
    return [present_campaign(r, await _counts(db, r.id)) for r in rows]


async def _audience(db: AsyncSession, tenant_id: str, audience: str) -> list[dict]:
    """People with the fields a message needs. Consent is applied by the caller."""
    out: list[dict] = []
    if audience == "leads":
        for r in (await db.execute(select(m.GymLead).where(m.GymLead.tenant_id == tenant_id, m.GymLead.status.in_(OPEN)))).scalars().all():
            out.append({"lead_id": r.id, "member_id": None, "name": r.full_name, "phone": r.phone, "email": r.email, "consent": bool(r.marketing_consent)})
        return out
    members = (await db.execute(select(m.GymMember).where(m.GymMember.tenant_id == tenant_id))).scalars().all()
    ending = {x["member_id"] for x in await expiring(db, tenant_id)} if audience == "expiring" else set()
    today = date.today()
    for mem in members:
        state = _state(await _latest(db, tenant_id, mem.id), today)
        if audience == "active" and state != "active":
            continue
        if audience == "lapsed" and state not in ("expired", "cancelled"):
            continue
        if audience == "expiring" and mem.id not in ending:
            continue
        out.append({"lead_id": None, "member_id": mem.id, "name": mem.full_name, "phone": mem.phone, "email": mem.email, "consent": bool(mem.marketing_consent)})
    return out


async def send_campaign(db: AsyncSession, tenant_id: str, campaign_id: str, *, user_id) -> dict:
    camp = (await db.execute(select(m.GymCampaign).where(m.GymCampaign.id == campaign_id, m.GymCampaign.tenant_id == tenant_id).with_for_update())).scalar_one_or_none()
    if camp is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if camp.status != "draft":
        raise HTTPException(status_code=409, detail="This campaign was already sent. Use retry for the ones that failed.")
    people = await _audience(db, tenant_id, camp.audience)
    if len(people) > MAX_SEND:
        raise HTTPException(status_code=422, detail=f"That audience is over {MAX_SEND}. Narrow it down first.")
    tenant = await db.get(m.Tenant, tenant_id)
    marketing = camp.kind == "marketing"
    emails = [p["email"] for p in people if p["email"]]
    suppressed = await privacy.suppressed_among(db, emails) if (marketing and camp.channel == "email") else set()
    seen: set[str] = set()
    for p in people:
        address = (p["email"] if camp.channel == "email" else p["phone"]) or ""
        address = privacy.normalize_email(address) if camp.channel == "email" else sms_svc.normalize_phone(address) or ""
        rec = m.GymCampaignRecipient(tenant_id=tenant_id, campaign_id=camp.id, member_id=p["member_id"], lead_id=p["lead_id"], address=address or f"none:{p['member_id'] or p['lead_id']}")
        if not address:
            rec.status, rec.detail = "skipped", f"No {'email' if camp.channel == 'email' else 'phone number'}"
        elif address in seen:
            continue  # two people sharing one address get one message
        elif marketing and not p["consent"]:
            rec.status, rec.detail = "skipped", "Has not agreed to marketing"
        elif address in suppressed:
            rec.status, rec.detail = "skipped", "Unsubscribed"
        else:
            seen.add(address)
            rec.status = "queued"
        db.add(rec)
        if rec.status == "queued":
            await _deliver(camp, rec, p, tenant, marketing)
    camp.status, camp.sent_at = "sent", datetime.utcnow()
    await db.flush()
    counts = await _counts(db, camp.id)
    await _audit(db, tenant_id, user_id, "gym_campaign_sent", "gym_campaign", camp.id, counts)
    return present_campaign(camp, counts)


async def _deliver(camp: m.GymCampaign, rec: m.GymCampaignRecipient, person: dict, tenant, marketing: bool) -> None:
    text = camp.message.replace("{name}", person["name"].split(" ")[0])
    if camp.channel == "sms":
        res = await sms_svc.send_sms(to=rec.address, body=text, tenant=tenant)
        ok, mode, err = res.sent, res.mode, res.error
    else:
        headers = privacy.list_unsubscribe_headers(rec.address) if marketing else None
        body = text + (f"\n\nStop these emails: {privacy.unsubscribe_page_url(rec.address)}" if marketing else "")
        res = await emailer.send_email(to=rec.address, subject=camp.subject or camp.name, text_body=body, tenant=tenant, extra_headers=headers)
        ok, mode, err = res.sent, res.mode, res.error
    if ok:
        rec.status, rec.sent_at, rec.detail = "sent", datetime.utcnow(), f"via {mode}"
    else:
        rec.status, rec.detail = "failed", (err or ("Channel is switched off" if mode == "disabled" else "Not delivered"))[:300]


async def retry_failed(db: AsyncSession, tenant_id: str, campaign_id: str, *, user_id) -> dict:
    camp = (await db.execute(select(m.GymCampaign).where(m.GymCampaign.id == campaign_id, m.GymCampaign.tenant_id == tenant_id).with_for_update())).scalar_one_or_none()
    if camp is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    tenant = await db.get(m.Tenant, tenant_id)
    failed = (await db.execute(select(m.GymCampaignRecipient).where(m.GymCampaignRecipient.campaign_id == camp.id, m.GymCampaignRecipient.status == "failed"))).scalars().all()
    for rec in failed:
        person = {"name": "there"}
        if rec.member_id:
            mem = await db.get(m.GymMember, rec.member_id)
            person["name"] = mem.full_name if mem else "there"
        elif rec.lead_id:
            lead = await db.get(m.GymLead, rec.lead_id)
            person["name"] = lead.full_name if lead else "there"
        await _deliver(camp, rec, person, tenant, camp.kind == "marketing")
    await db.flush()
    counts = await _counts(db, camp.id)
    await _audit(db, tenant_id, user_id, "gym_campaign_retried", "gym_campaign", camp.id, counts)
    return present_campaign(camp, counts)


async def run_renewal_reminders(db: AsyncSession, tenant_id: str, *, channel: str, user_id) -> dict:
    """Remind members whose plan ends within 7 days. Safe to press twice: once per channel per day."""
    day = date.today().isoformat()
    name = f"Renewal reminders {day} ({channel})"
    taken = (await db.execute(select(m.GymCampaign.id).where(m.GymCampaign.tenant_id == tenant_id, m.GymCampaign.name == name))).first()
    if taken:
        raise HTTPException(status_code=409, detail="Today's reminders were already sent on this channel.")
    tenant = await db.get(m.Tenant, tenant_id)
    company = (getattr(tenant, "company_name", None) or "your gym").strip()
    camp = m.GymCampaign(
        tenant_id=tenant_id, name=name, channel=channel, audience="expiring", kind="service", created_by=user_id,
        subject=f"Your {company} membership ends soon",
        message=f"Hi {{name}}, your membership at {company} ends soon. Visit the front desk to renew and keep training without a break.",
    )
    db.add(camp)
    await db.flush()
    return await send_campaign(db, tenant_id, camp.id, user_id=user_id)


async def reminder_setting(db: AsyncSession, tenant_id: str) -> str:
    row = (await db.execute(select(m.GymSettings).where(m.GymSettings.tenant_id == tenant_id))).scalar_one_or_none()
    return (row.reminder_channels if row else "") or ""


async def set_reminder_setting(db: AsyncSession, tenant_id: str, channels: str, *, user_id) -> dict:
    """Turn the daily renewal reminder on or off. Off by default, so nobody gets texts they did not ask for."""
    row = (await db.execute(select(m.GymSettings).where(m.GymSettings.tenant_id == tenant_id).with_for_update())).scalar_one_or_none()
    if row is None:
        row = m.GymSettings(tenant_id=tenant_id)
        db.add(row)
    row.reminder_channels = channels
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_auto_reminders_set", "gym_settings", row.id, {"channels": channels})
    return {"reminder_channels": channels}


async def campaign_recipients(db: AsyncSession, tenant_id: str, campaign_id: str) -> list[dict]:
    camp = await db.get(m.GymCampaign, campaign_id)
    if camp is None or camp.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    rows = (await db.execute(select(m.GymCampaignRecipient).where(m.GymCampaignRecipient.campaign_id == campaign_id).order_by(m.GymCampaignRecipient.status))).scalars().all()
    return [{"id": r.id, "address": r.address, "status": r.status, "detail": r.detail} for r in rows]
