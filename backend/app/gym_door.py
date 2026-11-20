"""Gym door: credentials (QR / card / RFID / NFC / barcode), scans, devices and offline sync.

Security rules:
- Only a hash of a credential token is stored. The token is shown once when it is issued.
- A revoked credential, or a member who is not active, is never let in.
- Offline scans are checked again when they sync. A scan older than OFFLINE_MAX_HOURS is not
  trusted; it is recorded and flagged for staff instead of being turned into a visit.
- A device's own event id makes a retried sync harmless: the same event never counts twice.
- Devices are `verified=false` until someone has tested them on real hardware. Nothing here
  claims a reader or turnstile works; it only gives it a safe place to send scans.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import gym as base
from app import models as m
from app.gym import _audit, _member
from app.honesty import optional_honest_narrative, require_honest_narrative

OFFLINE_MAX_HOURS = 24
MAX_BATCH = 200
KINDS = ("qr", "card", "rfid", "nfc", "barcode")
DEVICE_KINDS = ("qr_scanner", "barcode_scanner", "rfid_reader", "nfc_reader", "fingerprint", "face", "turnstile")


def qr_image(token: str) -> str:
    """The code as a PNG data URI a screen can show. Drawn here so no browser library is needed."""
    import base64

    from app.barcodes import render_qr_png

    return "data:image/png;base64," + base64.b64encode(render_qr_png(token, box_size=6, border=2)).decode("ascii")


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").strip().encode()).hexdigest()


def present_credential(row: m.GymCredential) -> dict:
    return {"id": row.id, "member_id": row.member_id, "kind": row.kind, "label": row.label, "status": row.status}


async def issue_credential(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    member = await _member(db, tenant_id, payload.member_id)
    if payload.token:
        # A card or tag that already carries its own number: staff scan it in once.
        token = payload.token.strip()
        if len(token) < 4:
            raise HTTPException(status_code=422, detail="That card number is too short")
    else:
        token = "gym_" + secrets.token_urlsafe(24)
    digest = hash_token(token)
    if (await db.execute(select(m.GymCredential.id).where(m.GymCredential.token_hash == digest))).first():
        raise HTTPException(status_code=409, detail="That card or code is already in use")
    row = m.GymCredential(
        tenant_id=tenant_id, member_id=member.id, kind=payload.kind, token_hash=digest, created_by=user_id,
        label=optional_honest_narrative(payload.label, label="label", max_length=80),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_credential_issued", "gym_credential", row.id, {"member_id": member.id, "kind": payload.kind})
    return {**present_credential(row), "token": token, "member_name": member.full_name, "qr_png": qr_image(token)}


async def list_credentials(db: AsyncSession, tenant_id: str, member_id: str) -> list[dict]:
    await _member(db, tenant_id, member_id)
    rows = (
        await db.execute(select(m.GymCredential).where(m.GymCredential.tenant_id == tenant_id, m.GymCredential.member_id == member_id))
    ).scalars().all()
    return [present_credential(r) for r in rows]


async def revoke_credential(db: AsyncSession, tenant_id: str, credential_id: str, *, user_id) -> dict:
    row = await db.get(m.GymCredential, credential_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Credential not found")
    if row.status == "revoked":
        raise HTTPException(status_code=409, detail="Already revoked")
    row.status, row.revoked_at = "revoked", datetime.utcnow()
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_credential_revoked", "gym_credential", row.id, {})
    return present_credential(row)


async def _member_for_token(db: AsyncSession, tenant_id: str, token: str) -> tuple[m.GymMember | None, str | None]:
    row = (
        await db.execute(select(m.GymCredential).where(m.GymCredential.token_hash == hash_token(token), m.GymCredential.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row is None:
        return None, "Card or code not recognised"
    if row.status != "active":
        return None, "This card or code was cancelled"
    return await db.get(m.GymMember, row.member_id), None


async def scan(db: AsyncSession, tenant_id: str, *, token: str, branch_id: str | None, user_id) -> dict:
    member, problem = await _member_for_token(db, tenant_id, token)
    if member is None:
        return {"allowed": False, "already_in": False, "message": problem}
    return await base.check_in(db, tenant_id, member_id=member.id, user_id=user_id, branch_id=branch_id)


# --- Devices --------------------------------------------------------------------------------


def present_device(row: m.GymDevice) -> dict:
    return {
        "id": row.id, "name": row.name, "kind": row.kind, "branch_id": row.branch_id, "is_active": bool(row.is_active),
        "verified": bool(row.verified), "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "status": "tested on hardware" if row.verified else "not yet tested on real hardware",
    }


async def register_device(db: AsyncSession, tenant_id: str, payload, *, user_id) -> dict:
    if payload.branch_id:
        from app import gym_access

        await gym_access.usable_branch(db, tenant_id, payload.branch_id)
    row = m.GymDevice(
        tenant_id=tenant_id, branch_id=payload.branch_id, kind=payload.kind,
        name=require_honest_narrative(payload.name, label="device name", max_length=120),
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_device_registered", "gym_device", row.id, {"kind": payload.kind})
    return present_device(row)


async def list_devices(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (await db.execute(select(m.GymDevice).where(m.GymDevice.tenant_id == tenant_id).order_by(m.GymDevice.name))).scalars().all()
    return [present_device(r) for r in rows]


async def mark_device_verified(db: AsyncSession, tenant_id: str, device_id: str, *, verified: bool, user_id) -> dict:
    row = await db.get(m.GymDevice, device_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Device not found")
    row.verified = verified
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_device_verified" if verified else "gym_device_unverified", "gym_device", row.id, {})
    return present_device(row)


# --- Offline sync ---------------------------------------------------------------------------


async def roster(db: AsyncSession, tenant_id: str) -> dict:
    """What a reader may cache for offline use: credential hash -> member and valid-until, active members only."""
    today = date.today()
    out = []
    creds = (
        await db.execute(select(m.GymCredential).where(m.GymCredential.tenant_id == tenant_id, m.GymCredential.status == "active"))
    ).scalars().all()
    for c in creds:
        member = await db.get(m.GymMember, c.member_id)
        current = await base._latest(db, tenant_id, c.member_id)
        if member is None or base._state(current, today) != "active":
            continue
        out.append({"token_hash": c.token_hash, "member_id": member.id, "member_name": member.full_name, "valid_until": current.ends_on.isoformat()})
    return {"generated_at": datetime.utcnow().isoformat(), "trust_hours": OFFLINE_MAX_HOURS, "entries": out}


async def sync_events(db: AsyncSession, tenant_id: str, *, device_id: str | None, events: list, user_id) -> dict:
    if len(events) > MAX_BATCH:
        raise HTTPException(status_code=422, detail=f"Send at most {MAX_BATCH} scans at a time")
    device = None
    if device_id:
        device = await db.get(m.GymDevice, device_id)
        if device is None or device.tenant_id != tenant_id or not device.is_active:
            raise HTTPException(status_code=404, detail="Device not found")
        device.last_seen_at = datetime.utcnow()
    now = datetime.now(timezone.utc)
    results = []
    for ev in sorted(events, key=lambda e: e.occurred_at):
        seen = (await db.execute(select(m.GymDoorEvent).where(m.GymDoorEvent.tenant_id == tenant_id, m.GymDoorEvent.event_id == ev.event_id))).scalar_one_or_none()
        if seen is not None:
            results.append({"event_id": ev.event_id, "outcome": seen.outcome, "message": seen.message, "duplicate": True})
            continue
        at = ev.occurred_at if ev.occurred_at.tzinfo else ev.occurred_at.replace(tzinfo=timezone.utc)
        if at > now + timedelta(minutes=5):
            outcome, message, member_id, attention = "refused", "The scan is dated in the future", None, True
        elif now - at > timedelta(hours=OFFLINE_MAX_HOURS):
            outcome, message, member_id, attention = "too_old", f"Older than {OFFLINE_MAX_HOURS} hours, not trusted", None, True
        else:
            member, problem = await _member_for_token(db, tenant_id, ev.token)
            if member is None:
                outcome, message, member_id, attention = "unknown", problem, None, True
            else:
                member_id = member.id
                # A savepoint keeps one bad scan from undoing the rest of the batch.
                async with db.begin_nested():
                    res = await base.check_in(db, tenant_id, member_id=member.id, user_id=user_id, branch_id=ev.branch_id, at=at)
                outcome = "allowed" if res["allowed"] else "refused"
                message = res["message"]
                # Someone was let in on the device's say-so but the membership says no: staff must look.
                attention = not res["allowed"]
        db.add(
            m.GymDoorEvent(
                tenant_id=tenant_id, event_id=ev.event_id, device_id=device.id if device else None, member_id=member_id,
                occurred_at=at.astimezone(timezone.utc).replace(tzinfo=None), outcome=outcome, message=(message or "")[:200], needs_attention=attention,
            )
        )
        await db.flush()
        results.append({"event_id": ev.event_id, "outcome": outcome, "message": message, "duplicate": False})
    return {"results": results, "accepted": sum(1 for r in results if r["outcome"] == "allowed" and not r["duplicate"])}


async def attention_list(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(
            select(m.GymDoorEvent)
            .where(m.GymDoorEvent.tenant_id == tenant_id, m.GymDoorEvent.needs_attention.is_(True))
            .order_by(m.GymDoorEvent.occurred_at.desc()).limit(100)
        )
    ).scalars().all()
    return [{"id": r.id, "event_id": r.event_id, "outcome": r.outcome, "message": r.message, "occurred_at": r.occurred_at.isoformat(), "member_id": r.member_id} for r in rows]


async def clear_attention(db: AsyncSession, tenant_id: str, event_row_id: str, *, user_id) -> dict:
    row = await db.get(m.GymDoorEvent, event_row_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Event not found")
    row.needs_attention = False
    await db.flush()
    await _audit(db, tenant_id, user_id, "gym_door_event_reviewed", "gym_door_event", row.id, {})
    return {"id": row.id}
