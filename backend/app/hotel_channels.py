"""Hotel channel sync over iCal: Booking.com, Expedia, Airbnb and any site that shares a calendar.

Each room gets a feed. We publish the room's bookings at `/api/v1/hotel-calendar/<token>.ics`,
which the booking site reads to close those dates. We read the site's own calendar
(`import_url`) and turn each booking there into a stay on the room, so the room cannot be sold
twice. A booking that disappears from the site's calendar is cancelled here, unless the guest
has already arrived. iCal carries dates, not guest details or prices: staff fill those in.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.honesty import money_json

CHANNEL_LABELS = {
    "booking_com": "Booking.com",
    "expedia": "Expedia",
    "airbnb": "Airbnb",
    "other": "Booking site",
}
MAX_FEED_BYTES = 2_000_000
FETCH_TIMEOUT_SECONDS = 20
# How far ahead we publish and accept bookings.
HORIZON_DAYS = 400


def serialize_feed(row: m.HotelChannelFeed, *, base_url: str | None = None, room_code: str | None = None) -> dict:
    path = f"/api/v1/hotel-calendar/{row.export_token}.ics"
    return {
        "id": row.id,
        "room_id": row.room_id,
        "room_code": room_code,
        "channel": row.channel,
        "channel_label": CHANNEL_LABELS.get(row.channel, "Booking site"),
        "import_url": row.import_url,
        "export_path": path,
        "export_url": f"{base_url.rstrip('/')}{path}" if base_url else path,
        "is_active": bool(row.is_active),
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "last_status": row.last_status,
    }


async def list_feeds(db: AsyncSession, *, tenant_id: str) -> list[tuple[m.HotelChannelFeed, str | None]]:
    rows = (
        await db.execute(
            select(m.HotelChannelFeed, m.HotelRoom.code)
            .join(m.HotelRoom, m.HotelRoom.id == m.HotelChannelFeed.room_id)
            .where(m.HotelChannelFeed.tenant_id == tenant_id)
            .order_by(m.HotelRoom.code, m.HotelChannelFeed.channel)
        )
    ).all()
    return [(r[0], r[1]) for r in rows]


async def _feed(db: AsyncSession, tenant_id: str, feed_id: str) -> m.HotelChannelFeed:
    row = (
        await db.execute(
            select(m.HotelChannelFeed).where(
                m.HotelChannelFeed.id == feed_id, m.HotelChannelFeed.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Channel link not found")
    return row


async def create_feed(
    db: AsyncSession,
    *,
    tenant_id: str,
    room_id: str,
    channel: str,
    import_url: str | None,
    created_by: str | None,
) -> m.HotelChannelFeed:
    room = (
        await db.execute(select(m.HotelRoom).where(m.HotelRoom.id == room_id, m.HotelRoom.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    clash = (
        await db.execute(
            select(m.HotelChannelFeed.id).where(
                m.HotelChannelFeed.tenant_id == tenant_id,
                m.HotelChannelFeed.room_id == room_id,
                m.HotelChannelFeed.channel == channel,
            )
        )
    ).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail=f"Room {room.code} is already linked to {CHANNEL_LABELS.get(channel, channel)}")
    row = m.HotelChannelFeed(
        tenant_id=tenant_id,
        room_id=room_id,
        channel=channel,
        import_url=import_url,
        export_token=secrets.token_urlsafe(32)[:48],
        created_by=created_by,
    )
    db.add(row)
    await db.flush()
    return row


async def update_feed(
    db: AsyncSession,
    *,
    tenant_id: str,
    feed_id: str,
    import_url: str | None = None,
    clear_import_url: bool = False,
    is_active: bool | None = None,
) -> m.HotelChannelFeed:
    row = await _feed(db, tenant_id, feed_id)
    if clear_import_url:
        row.import_url = None
    elif import_url:
        row.import_url = import_url
    if is_active is not None:
        row.is_active = bool(is_active)
    await db.flush()
    return row


async def delete_feed(db: AsyncSession, *, tenant_id: str, feed_id: str) -> None:
    row = await _feed(db, tenant_id, feed_id)
    await db.delete(row)
    await db.flush()


# --- Publishing our calendar -------------------------------------------------------------------


def _ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """iCal lines stay under 75 octets; longer ones continue on a line starting with a space."""
    out, raw = [], line.encode("utf-8")
    while len(raw) > 73:
        cut = 73
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


async def export_calendar(db: AsyncSession, *, token: str) -> str:
    """The room's taken nights, for a booking site to close. No guest names or prices leave the hotel."""
    feed = (
        await db.execute(
            select(m.HotelChannelFeed).where(
                m.HotelChannelFeed.export_token == token, m.HotelChannelFeed.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if feed is None:
        raise HTTPException(status_code=404, detail="Calendar not found")
    today = date.today()
    stays = (
        await db.execute(
            select(m.HotelReservation).where(
                m.HotelReservation.tenant_id == feed.tenant_id,
                m.HotelReservation.room_id == feed.room_id,
                m.HotelReservation.status.in_(("tentative", "booked", "checked_in")),
                m.HotelReservation.check_out_date > today - timedelta(days=1),
                m.HotelReservation.check_in_date < today + timedelta(days=HORIZON_DAYS),
            )
        )
    ).scalars().all()
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RIBDIGI ERP//Hotel calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for stay in stays:
        # A booking that came from this very site is already on its calendar: do not send it back.
        if getattr(stay, "channel_feed_id", None) == feed.id:
            continue
        lines += [
            "BEGIN:VEVENT",
            f"UID:{stay.id}@ribdigi-hotel",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{stay.check_in_date.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{stay.check_out_date.strftime('%Y%m%d')}",
            _fold(f"SUMMARY:{_ics_escape('Not available')}"),
            "TRANSP:OPAQUE",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


# --- Reading the booking site's calendar -------------------------------------------------------


def _unfold(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and out:
            out[-1] += raw[1:]
        else:
            out.append(raw)
    return out


def _ics_date(value: str) -> date | None:
    digits = re.sub(r"[^0-9]", "", value or "")[:8]
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def parse_calendar(text: str) -> list[dict]:
    """VEVENTs as {uid, start, end, summary}. Events without both dates are skipped."""
    events: list[dict] = []
    current: dict | None = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current and current.get("start") and current.get("end") and current.get("uid"):
                if current["end"] <= current["start"]:
                    current["end"] = current["start"] + timedelta(days=1)
                if (current.get("status") or "").upper() != "CANCELLED":
                    events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        head, value = line.split(":", 1)
        name = head.split(";", 1)[0].upper()
        if name == "UID":
            current["uid"] = value.strip()[:255]
        elif name == "DTSTART":
            current["start"] = _ics_date(value)
        elif name == "DTEND":
            current["end"] = _ics_date(value)
        elif name == "SUMMARY":
            current["summary"] = value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ").strip()[:200]
        elif name == "STATUS":
            current["status"] = value.strip()
    return events


async def _fetch(url: str) -> str:
    from app.outbound import assert_public_destination, public_transport

    await assert_public_destination(url)
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS, transport=public_transport(), follow_redirects=False
    ) as client:
        res = await client.get(url, headers={"Accept": "text/calendar"})
    if res.status_code != 200:
        raise HTTPException(status_code=502, detail=f"The booking site answered {res.status_code}")
    body = res.content[:MAX_FEED_BYTES + 1]
    if len(body) > MAX_FEED_BYTES:
        raise HTTPException(status_code=502, detail="The booking site's calendar is too large")
    text = body.decode("utf-8", errors="replace")
    if "BEGIN:VCALENDAR" not in text:
        raise HTTPException(status_code=502, detail="That link is not a calendar (iCal) file")
    return text


async def _channel_guest(db: AsyncSession, tenant_id: str, label: str) -> m.HotelGuest:
    """One placeholder guest per site; staff put the real guest on the stay when details arrive."""
    name = f"{label} guest"
    guest = (
        await db.execute(
            select(m.HotelGuest).where(m.HotelGuest.tenant_id == tenant_id, m.HotelGuest.full_name == name)
        )
    ).scalars().first()
    if guest is None:
        guest = m.HotelGuest(tenant_id=tenant_id, full_name=name, notes="Stays imported from the booking site's calendar")
        db.add(guest)
        await db.flush()
    return guest


async def sync_feed(
    db: AsyncSession,
    *,
    tenant_id: str,
    feed: m.HotelChannelFeed,
    user_id: str | None = None,
    text: str | None = None,
) -> dict:
    """Bring the booking site's bookings into the room. Safe to repeat."""
    from app import hotel as hotel_svc

    if not feed.import_url and text is None:
        raise HTTPException(status_code=400, detail="Paste the booking site's calendar link first")
    label = CHANNEL_LABELS.get(feed.channel, "Booking site")
    try:
        events = parse_calendar(text if text is not None else await _fetch(feed.import_url or ""))
    except HTTPException as exc:
        feed.last_synced_at = datetime.utcnow()
        feed.last_status = f"Failed: {exc.detail}"[:500]
        await db.flush()
        raise
    today = await hotel_svc.hotel_today(db, tenant_id)
    events = [e for e in events if e["end"] > today and e["start"] < today + timedelta(days=HORIZON_DAYS)]
    ours = {
        r.channel_uid: r
        for r in (
            await db.execute(
                select(m.HotelReservation).where(
                    m.HotelReservation.tenant_id == tenant_id,
                    m.HotelReservation.channel_feed_id == feed.id,
                )
            )
        ).scalars().all()
        if r.channel_uid
    }
    added = moved = cancelled = 0
    clashes: list[str] = []
    seen: set[str] = set()
    room = await db.get(m.HotelRoom, feed.room_id)
    for event in events:
        uid = event["uid"]
        # Our own published nights come back on some sites' calendars: skip them.
        if uid.endswith("@ribdigi-hotel"):
            continue
        seen.add(uid)
        stay = ours.get(uid)
        if stay is not None:
            if stay.status in {"cancelled", "no_show", "checked_out"}:
                continue
            if (stay.check_in_date, stay.check_out_date) != (event["start"], event["end"]) and stay.status in {"booked", "tentative"}:
                try:
                    await hotel_svc.update_reservation(
                        db,
                        tenant_id=tenant_id,
                        reservation_id=stay.id,
                        check_in_date=event["start"],
                        check_out_date=event["end"],
                    )
                    moved += 1
                except HTTPException as exc:
                    clashes.append(f"{event['start']:%d %b}: {exc.detail}")
            continue
        try:
            async with hotel_svc.room_booking_lock(tenant_id, feed.room_id):
                guest = await _channel_guest(db, tenant_id, label)
                row, _room, _guest = await hotel_svc.create_reservation(
                    db,
                    tenant_id=tenant_id,
                    room_id=feed.room_id,
                    guest_id=guest.id,
                    check_in_date=event["start"],
                    check_out_date=event["end"],
                    nightly_rate=None,
                    booking_source="ota",
                    notes=f"From {label}: {event.get('summary') or 'booking'}"[:500],
                    created_by=user_id,
                )
            row.channel_feed_id = feed.id
            row.channel_uid = uid
            added += 1
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            clashes.append(f"{event['start']:%d %b}–{event['end']:%d %b}: {detail}")
    for uid, stay in ours.items():
        if uid in seen or stay.status not in {"booked", "tentative"}:
            continue
        if stay.check_out_date <= today:
            continue
        await hotel_svc.cancel_reservation(db, tenant_id=tenant_id, reservation_id=stay.id)
        stay.notes = f"{stay.notes or ''} Cancelled on {label}.".strip()[:500]
        cancelled += 1
    status = f"{added} new, {moved} changed, {cancelled} cancelled"
    if clashes:
        status += f". Double booking, check now: {'; '.join(clashes)}"
    feed.last_synced_at = datetime.utcnow()
    feed.last_status = status[:500]
    await db.flush()
    if clashes:
        await _alert_clash(db, tenant_id=tenant_id, label=label, room=room, clashes=clashes)
    return {"added": added, "changed": moved, "cancelled": cancelled, "clashes": clashes, "status": status}


async def _alert_clash(db: AsyncSession, *, tenant_id: str, label: str, room, clashes: list[str]) -> None:
    try:
        from app import notifications as notifications_svc

        await notifications_svc.create_notification(
            db,
            tenant_id=tenant_id,
            roles=["hotel_manager", "company_admin", "hotel_front_desk"],
            category="system",
            entity_type="hotel_channel_feed",
            title=f"{label} booking clashes with room {getattr(room, 'code', '')}",
            message="; ".join(clashes)[:900],
        )
    except Exception:  # noqa: BLE001 - the clash is still on the channel status line
        pass


async def sync_all(db: AsyncSession, *, tenant_id: str) -> dict:
    feeds = (
        await db.execute(
            select(m.HotelChannelFeed).where(
                m.HotelChannelFeed.tenant_id == tenant_id,
                m.HotelChannelFeed.is_active.is_(True),
                m.HotelChannelFeed.import_url.is_not(None),
            )
        )
    ).scalars().all()
    done = failed = 0
    for feed in feeds:
        try:
            async with db.begin_nested():
                await sync_feed(db, tenant_id=tenant_id, feed=feed)
            done += 1
        except Exception:  # noqa: BLE001 - one site's outage must not stop the others
            failed += 1
    return {"synced": done, "failed": failed}
