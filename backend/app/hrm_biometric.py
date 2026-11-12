"""ZKTeco fingerprint / face terminals feeding HRM clock times.

Two ways in, both mapped to staff by the PIN on the terminal (HrmEmployee.biometric_id):

1. **BioTime pull.** The company's ZKTeco BioTime server (8.x web API) is linked with its
   address and an API user. "Sync now" signs in (`POST /jwt-api-token-auth/`, falling back
   to `/api-token-auth/`) and reads `GET /iclock/api/transactions/` page by page from the
   last sync. The BioTime server must be reachable from the ERP over the internet.
2. **Terminal push (ZKTeco ADMS / "cloud server").** A terminal pointed at the ERP's
   address calls `/iclock/cdata` and `/iclock/getrequest`. It is found by its serial
   number, which must be registered first. The protocol has no password: anyone who knows
   a registered serial could send punches, so punches are marked `biometric` and stay on
   the daily sheet for HR to check.

Every punch is stored once (`external_ref`), whichever way it arrives. Punch state
0 / 3 / 4 is in, 1 / 2 / 5 is out; anything else alternates with the person's last punch.
Built against ZKTeco's published behaviour and tested with simulated traffic only: it
must be checked against a real terminal and BioTime server before it is relied on.
"""

from __future__ import annotations

import ipaddress
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import InvalidToken
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import require_honest_narrative
from app.secret_keys import secret_fernet

IN_STATES = {"0", "3", "4"}
OUT_STATES = {"1", "2", "5"}
MAX_PAGES = 50
# Tests swap this for an httpx.MockTransport.
transport: httpx.AsyncBaseTransport | None = None


def _fernet():
    return secret_fernet(b"ribdigi-hrm-biotime-v1")


def _encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Cannot read the BioTime password. Save it again.") from exc


def check_base_url(url: str) -> str:
    """An http(s) address, not a cloud metadata or loopback address."""
    text = (url or "").strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Enter the BioTime address, e.g. https://biotime.example.com")
    host = parsed.hostname.lower()
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".internal"):
        raise HTTPException(status_code=422, detail="That address cannot be reached from the ERP")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
            raise HTTPException(status_code=422, detail="That address cannot be reached from the ERP")
    except ValueError:
        pass
    return text


def serialize_link(row: m.HrmBiometricLink) -> dict:
    return {
        "id": row.id, "kind": row.kind, "name": row.name, "base_url": row.base_url, "username": row.username,
        "has_password": bool(row.password_enc), "device_serial": row.device_serial, "site_id": row.site_id,
        "last_synced_at": row.last_synced_at.isoformat() + "Z" if row.last_synced_at else None,
        "last_seen_at": row.last_seen_at.isoformat() + "Z" if row.last_seen_at else None,
        "last_result": row.last_result, "is_active": bool(row.is_active),
    }


async def list_links(db: AsyncSession, tenant_id: str) -> list[m.HrmBiometricLink]:
    return list((await db.execute(select(m.HrmBiometricLink).where(m.HrmBiometricLink.tenant_id == tenant_id).order_by(m.HrmBiometricLink.name))).scalars())


async def add_link(db: AsyncSession, tenant_id: str, payload, *, user_id) -> m.HrmBiometricLink:
    from app import hrm

    name = require_honest_narrative(payload.name, label="name", max_length=120)
    row = m.HrmBiometricLink(tenant_id=tenant_id, kind=payload.kind, name=name, is_active=True, created_by=user_id)
    if payload.kind == "biotime":
        if not payload.base_url or not payload.username or not payload.password:
            raise HTTPException(status_code=422, detail="BioTime needs its address, an API user and its password")
        row.base_url = check_base_url(payload.base_url)
        row.username = payload.username.strip()
        row.password_enc = _encrypt(payload.password)
        # Start from the beginning of this month the first time.
        today = datetime.utcnow()
        row.last_synced_at = datetime(today.year, today.month, 1)
    else:
        serial = (payload.device_serial or "").strip().upper()
        if not serial:
            raise HTTPException(status_code=422, detail="Enter the terminal's serial number")
        taken = (await db.execute(select(m.HrmBiometricLink.id).where(m.HrmBiometricLink.device_serial == serial))).first()
        if taken:
            raise HTTPException(status_code=409, detail="That serial number is already linked")
        row.device_serial = serial
    if payload.site_id:
        site = await db.get(m.HrmSite, payload.site_id)
        if site is None or site.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Site not found")
        row.site_id = site.id
    db.add(row)
    await db.flush()
    await hrm._audit(db, tenant_id, user_id, "hrm_biometric_linked", "hrm_biometric_link", row.id, {"kind": row.kind, "name": name})
    return row


async def unlink(db: AsyncSession, tenant_id: str, link_id: str, *, user_id) -> m.HrmBiometricLink:
    from app import hrm

    row = await db.get(m.HrmBiometricLink, link_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Link not found")
    row.is_active = False
    await hrm._audit(db, tenant_id, user_id, "hrm_biometric_unlinked", "hrm_biometric_link", row.id, {})
    await db.flush()
    return row


async def _zone(db: AsyncSession, tenant_id: str) -> ZoneInfo:
    from app import hrm_time

    return await hrm_time._zone(db, tenant_id)


def _local_to_utc(text: str, zone: ZoneInfo) -> datetime:
    value = datetime.fromisoformat(text.strip().replace("T", " ")[:19])
    return value.replace(tzinfo=zone).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


async def ingest(
    db: AsyncSession, tenant_id: str, *, pin: str, at_utc: datetime, state: str | None, ref: str, site_id: str | None
) -> str:
    """Store one punch. Returns stored | duplicate | unknown_pin | left."""
    exists = (
        await db.execute(select(m.HrmClockEvent.id).where(m.HrmClockEvent.tenant_id == tenant_id, m.HrmClockEvent.external_ref == ref))
    ).first()
    if exists:
        return "duplicate"
    pin = (pin or "").strip()
    person = (
        await db.execute(
            select(m.HrmEmployee).where(m.HrmEmployee.tenant_id == tenant_id, m.HrmEmployee.biometric_id == pin)
        )
    ).scalars().first() if pin else None
    if person is None:
        return "unknown_pin"
    if person.status != "active":
        return "left"
    code = str(state or "").strip()
    if code in IN_STATES:
        kind = "in"
    elif code in OUT_STATES:
        kind = "out"
    else:
        last = (
            await db.execute(
                select(m.HrmClockEvent)
                .where(m.HrmClockEvent.employee_id == person.id, m.HrmClockEvent.voided.is_(False), m.HrmClockEvent.at < at_utc)
                .order_by(m.HrmClockEvent.at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        open_in = last is not None and last.kind == "in" and (at_utc - last.at) < timedelta(hours=20)
        kind = "out" if open_in else "in"
    db.add(
        m.HrmClockEvent(
            tenant_id=tenant_id, employee_id=person.id, kind=kind, at=at_utc, source="biometric",
            site_id=site_id, external_ref=ref[:80],
        )
    )
    await db.flush()
    return "stored"


def _tally(counts: dict, outcome: str) -> None:
    counts[outcome] = counts.get(outcome, 0) + 1


async def sync_biotime(db: AsyncSession, tenant_id: str, link_id: str, *, user_id=None) -> dict:
    from app import hrm

    link = await db.get(m.HrmBiometricLink, link_id)
    if link is None or link.tenant_id != tenant_id or link.kind != "biotime":
        raise HTTPException(status_code=404, detail="BioTime link not found")
    if not link.is_active:
        raise HTTPException(status_code=409, detail="This link is switched off")
    zone = await _zone(db, tenant_id)
    since_utc = (link.last_synced_at or datetime.utcnow() - timedelta(days=7)) - timedelta(minutes=10)
    until_utc = datetime.utcnow()
    fmt = lambda d: d.replace(tzinfo=ZoneInfo("UTC")).astimezone(zone).strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    counts: dict[str, int] = {}
    password = _decrypt(link.password_enc or "")
    try:
        async with httpx.AsyncClient(base_url=link.base_url, timeout=20, transport=transport) as client:
            auth = None
            for path, prefix in (("/jwt-api-token-auth/", "JWT"), ("/api-token-auth/", "Token")):
                r = await client.post(path, json={"username": link.username, "password": password})
                if r.status_code == 200 and r.json().get("token"):
                    auth = f"{prefix} {r.json()['token']}"
                    break
            if auth is None:
                raise HTTPException(status_code=502, detail="BioTime refused the sign-in. Check the user and password.")
            url = "/iclock/api/transactions/"
            params = {"start_time": fmt(since_utc), "end_time": fmt(until_utc), "page_size": 200, "page": 1}
            for _ in range(MAX_PAGES):
                r = await client.get(url, params=params, headers={"Authorization": auth})
                if r.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"BioTime answered {r.status_code} when reading punches")
                body = r.json()
                for row in body.get("data") or []:
                    outcome = await ingest(
                        db, tenant_id, pin=str(row.get("emp_code") or ""),
                        at_utc=_local_to_utc(str(row.get("punch_time")), zone),
                        state=row.get("punch_state"), ref=f"bt:{link.id}:{row.get('id')}", site_id=link.site_id,
                    )
                    _tally(counts, outcome)
                if not body.get("next"):
                    break
                params["page"] += 1
    except httpx.HTTPError as exc:
        link.last_result = f"Could not reach BioTime: {type(exc).__name__}"
        await db.flush()
        raise HTTPException(status_code=502, detail="Could not reach the BioTime server") from exc
    link.last_synced_at = until_utc
    link.last_result = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(counts.items())) or "No new punches"
    await hrm._audit(db, tenant_id, user_id, "hrm_biotime_synced", "hrm_biometric_link", link.id, counts)
    await db.flush()
    return {"counts": counts, "result": link.last_result, "synced_to": until_utc.isoformat() + "Z"}


# --- Terminal push (ZKTeco ADMS) ----------------------------------------------------------


async def device_for(db: AsyncSession, serial: str) -> m.HrmBiometricLink | None:
    serial = (serial or "").strip().upper()
    if not serial:
        return None
    row = (
        await db.execute(
            select(m.HrmBiometricLink).where(
                m.HrmBiometricLink.device_serial == serial,
                m.HrmBiometricLink.kind == "device",
                m.HrmBiometricLink.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        row.last_seen_at = datetime.utcnow()
    return row


def handshake_text(serial: str) -> str:
    """Options a ZKTeco terminal expects on GET /iclock/cdata?SN=…&options=all."""
    return "\n".join(
        [
            f"GET OPTION FROM: {serial}",
            "ATTLOGStamp=None",
            "OPERLOGStamp=9999",
            "ATTPHOTOStamp=None",
            "ErrorDelay=30",
            "Delay=10",
            "TransTimes=00:00;14:05",
            "TransInterval=1",
            "TransFlag=TransData AttLog",
            "TimeZone=0",
            "Realtime=1",
            "Encrypt=None",
        ]
    ) + "\n"


async def push_attlog(db: AsyncSession, link: m.HrmBiometricLink, body: str) -> dict:
    """ATTLOG lines: PIN<TAB>YYYY-MM-DD HH:MM:SS<TAB>state<TAB>verify…"""
    zone = await _zone(db, link.tenant_id)
    counts: dict[str, int] = {}
    for line in (body or "").splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 2 or not parts[0]:
            continue
        try:
            at_utc = _local_to_utc(parts[1], zone)
        except ValueError:
            _tally(counts, "bad_line")
            continue
        state = parts[2] if len(parts) > 2 else None
        outcome = await ingest(
            db, link.tenant_id, pin=parts[0], at_utc=at_utc, state=state,
            ref=f"zk:{link.device_serial}:{parts[0]}:{parts[1].strip()}", site_id=link.site_id,
        )
        _tally(counts, outcome)
    link.last_result = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(counts.items())) or "Nothing new"
    await db.flush()
    return counts
