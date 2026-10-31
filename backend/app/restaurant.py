"""Restaurant floor, kitchen, and recipe stock. Catalog products are the menu."""

from __future__ import annotations

import re
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import false as sql_false
from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app import accounting
from app import audit as audit_svc
from app import catalog as catalog_svc
from app import inventory
from app import models as m
from app.models import uid
from app import packages as packages_svc
from app import restaurant_till as till_svc
from app import schema_compat
from app.honesty import money_json, optional_honest_narrative, require_honest_narrative
from app.store_access import assert_store_access, assigned_store_ids

WASTE_REASONS = {"spoilage", "damage", "waste"}
WASTE_PREFIX = "[[waste:"
WASTE_SUFFIX = "]]"

SERVICE_MODES = {"dine_in", "takeaway", "delivery"}
COURSES = ("starter", "main", "dessert", "drink")
COURSE_RE = re.compile(r"\[\[course:([0-9a-fA-F-]{36}):(starter|main|dessert|drink)\]\]")
ITEM_NOTE_RE = re.compile(r"\[\[item:([0-9a-fA-F-]{36}):([^\]\n]{2,80})\]\]")
HOLD_RE = re.compile(r"\[\[hold:([0-9a-fA-F-]{36})\]\]")
SEAT_RE = re.compile(r"\[\[seat:([0-9a-fA-F-]{36}):([1-9]|[1-3][0-9]|40)\]\]")
SPICE_RE = re.compile(r"\[\[spice:([0-9a-fA-F-]{36}):(mild|medium|hot)\]\]")
SPICE_LEVELS = {"mild", "medium", "hot"}
DONENESS_RE = re.compile(r"\[\[doneness:([0-9a-fA-F-]{36}):(rare|medium|well)\]\]")
DONENESS_LEVELS = {"rare", "medium", "well"}
ZONE_RE = re.compile(r"\[\[zone:([^\]\n]{1,40})\]\]")
ZONES_KEY = "restaurant_delivery_zones"
CHANNEL_RE = re.compile(r"\[\[channel:online\]\]")
COVERS_RE = re.compile(r"\[\[covers:([1-9]|[1-3][0-9]|40)\]\]")
ALLERGY_RE = re.compile(r"\[\[allergy:([^\]\n]{2,80})\]\]")
OCCASION_RE = re.compile(r"\[\[occasion:([^\]\n]{2,80})\]\]")
PHONE_RE = re.compile(r"\[\[phone:(\+\d{8,15})\]\]")
PAGER_RE = re.compile(r"\[\[pager:([1-9]\d{0,2})\]\]")
READY_RE = re.compile(r"\[\[ready:([01]\d|2[0-3]):([0-5]\d)\]\]")
WAIT_RE = re.compile(r"\[\[wait:(180|1[0-7]\d|[1-9]\d|[5-9])\]\]")
FIRE_RE = re.compile(r"\[\[fire:([01]\d|2[0-3]):([0-5]\d)\]\]")
PACK_RE = re.compile(r"\[\[pack:(bag|box)\]\]")
PACKAGING = {"bag", "box"}
RUSH_RE = re.compile(r"\[\[rush\]\]")
RUSH_TOKEN = "[[rush]]"
BILL_RE = re.compile(r"\[\[bill\]\]")
BILL_TOKEN = "[[bill]]"
ARRIVED_RE = re.compile(r"\[\[arrived\]\]")
ARRIVED_TOKEN = "[[arrived]]"
RECEIPT_RE = re.compile(r"\[\[receipt:(print|email|declined)\]\]")
RECEIPTS = {"print", "email", "declined"}
CUTLERY_RE = re.compile(r"\[\[cutlery\]\]")
CUTLERY_TOKEN = "[[cutlery]]"
HIGHCHAIR_RE = re.compile(r"\[\[highchair\]\]")
HIGHCHAIR_TOKEN = "[[highchair]]"
DIET_RE = re.compile(r"\[\[diet:(vegetarian|vegan|halal)\]\]")
DIETS = {"vegetarian", "vegan", "halal"}
ALLERGEN_RE = re.compile(r"\[\[allergen:(nuts|gluten|dairy|shellfish)\]\]")
ALLERGENS = {"nuts", "gluten", "dairy", "shellfish"}
SOURCE_RE = re.compile(r"\[\[source:(walk_in|phone|booking)\]\]")
SOURCES = {"walk_in", "phone", "booking"}
VEHICLE_RE = re.compile(r"\[\[vehicle:([^\]\n]{2,80})\]\]")
BAY_RE = re.compile(r"\[\[bay:([1-9]|[1-3]\d|40)\]\]")
HANDOFF_RE = re.compile(r"\[\[handoff:(hand|door)\]\]")
HANDOFFS = {"hand", "door"}
EMAIL_RE = re.compile(r"\[\[email:([^\]\s]{3,120})\]\]")
CHANNEL_TOKEN = "[[channel:online]]"
ONLINE_KEY = "restaurant_online_orders"
FLOOR_KEY = "restaurant_floor_places"
SOUND_KEY = "restaurant_kitchen_sound"
CLOCK_KEY = "restaurant_clock"
SOLD_OUT_KEY = "restaurant_sold_out"
ROOM_KEY = "restaurant_table_rooms"
ROOMS = {"dining", "patio", "private"}
COOK_KEY = "restaurant_cook_times"
SERVINGS_KEY = "restaurant_recipe_servings"
SERVICE_KEY = "restaurant_service_percent"
DELIVER_PREFIX = "[[deliver-to:"
DELIVER_SUFFIX = "]]"


async def _line_prep_status_live(db: AsyncSession) -> bool:
    cols = await schema_compat.table_column_names(db, "restaurant_order_lines")
    return "prep_status" in cols


def _item_prep_status(line, ticket, *, has_prep: bool) -> str:
    if has_prep:
        return getattr(line, "prep_status", None) or "queued"
    if ticket is not None and ticket.status in {"ready", "done"}:
        return "ready"
    if ticket is not None and ticket.status == "preparing":
        return "preparing"
    return "queued"


def pack_waste_notes(*, reason: str, notes: str | None) -> str:
    leftover = (notes or "").strip()
    marker = f"{WASTE_PREFIX}{reason}{WASTE_SUFFIX}"
    return f"{marker} {leftover}".strip()


def unpack_waste_notes(raw: str | None) -> tuple[str | None, str | None]:
    text = raw or ""
    start = text.find(WASTE_PREFIX)
    if start < 0:
        return None, text.strip() or None
    end = text.find(WASTE_SUFFIX, start)
    if end < 0:
        return None, text.strip() or None
    reason = text[start + len(WASTE_PREFIX) : end].strip().lower() or None
    leftover = f"{text[:start]}{text[end + len(WASTE_SUFFIX):]}".strip() or None
    if reason not in WASTE_REASONS:
        return None, leftover
    return reason, leftover


def _strip_course_tokens(raw: str | None) -> str:
    return COURSE_RE.sub("", raw or "")


def _course_tokens(raw: str | None) -> list[str]:
    return [match.group(0) for match in COURSE_RE.finditer(raw or "")]


def course_for_line(raw: str | None, line_id: str) -> str:
    wanted = str(line_id).lower()
    for match in COURSE_RE.finditer(raw or ""):
        if match.group(1).lower() == wanted:
            return match.group(2)
    return "main"


def write_line_course(raw: str | None, line_id: str, course: str) -> str | None:
    kind = (course or "").strip().lower()
    if kind not in COURSES:
        raise HTTPException(status_code=422, detail="Course must be starter, main, dessert, or drink.")
    wanted = str(line_id).lower()
    without = COURSE_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    )
    tokens = _course_tokens(without)
    body = _strip_course_tokens(without).strip()
    if kind != "main":
        tokens.append(f"[[course:{line_id}:{kind}]]")
    parts = [part for part in [body, *tokens] if part]
    return "\n".join(parts) or None


def drop_line_course(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    without = COURSE_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    )
    tokens = _course_tokens(without)
    body = _strip_course_tokens(without).strip()
    parts = [part for part in [body, *tokens] if part]
    return "\n".join(parts) or None


def clean_item_note(value: str) -> str:
    text = str(value or "").strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not any(ch.isalnum() for ch in text)
    ):
        raise HTTPException(status_code=422, detail="Item note must be a plain note.")
    return text


def note_for_line(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    for match in ITEM_NOTE_RE.finditer(raw or ""):
        if match.group(1).lower() == wanted:
            return match.group(2).strip() or None
    return None


def write_line_note(raw: str | None, line_id: str, note: str) -> str | None:
    text = clean_item_note(note)
    wanted = str(line_id).lower()
    without = ITEM_NOTE_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    token = f"[[item:{line_id}:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_line_note(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    text = ITEM_NOTE_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    return text or None


def hold_for_line(raw: str | None, line_id: str) -> bool:
    wanted = str(line_id).lower()
    return any(match.group(1).lower() == wanted for match in HOLD_RE.finditer(raw or ""))


def write_line_hold(raw: str | None, line_id: str) -> str:
    without = drop_line_hold(raw, line_id) or ""
    token = f"[[hold:{line_id}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_line_hold(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    text = HOLD_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    return text or None


def clean_seat(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Seat must be a seat number.") from None
    if isinstance(value, bool) or number < 1 or number > 40:
        raise HTTPException(status_code=422, detail="Seat must be a seat number.")
    return number


def seat_for_line(raw: str | None, line_id: str) -> int | None:
    wanted = str(line_id).lower()
    for match in SEAT_RE.finditer(raw or ""):
        if match.group(1).lower() == wanted:
            return int(match.group(2))
    return None


def write_line_seat(raw: str | None, line_id: str, seat) -> str | None:
    number = clean_seat(seat)
    wanted = str(line_id).lower()
    without = SEAT_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    token = f"[[seat:{line_id}:{number}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_line_seat(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    text = SEAT_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    return text or None


def clean_spice(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Spice must be mild, medium, or hot.")
    text = str(value).strip().lower()
    if text not in SPICE_LEVELS:
        raise HTTPException(status_code=422, detail="Spice must be mild, medium, or hot.")
    return text


def spice_for_line(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    for match in SPICE_RE.finditer(raw or ""):
        if match.group(1).lower() == wanted:
            return match.group(2)
    return None


def write_line_spice(raw: str | None, line_id: str, spice) -> str | None:
    level = clean_spice(spice)
    wanted = str(line_id).lower()
    without = SPICE_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    token = f"[[spice:{line_id}:{level}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_line_spice(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    text = SPICE_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    return text or None


def clean_doneness(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Doneness must be rare, medium, or well.")
    text = str(value).strip().lower()
    if text not in DONENESS_LEVELS:
        raise HTTPException(status_code=422, detail="Doneness must be rare, medium, or well.")
    return text


def doneness_for_line(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    for match in DONENESS_RE.finditer(raw or ""):
        if match.group(1).lower() == wanted:
            return match.group(2)
    return None


def write_line_doneness(raw: str | None, line_id: str, doneness) -> str | None:
    level = clean_doneness(doneness)
    wanted = str(line_id).lower()
    without = DONENESS_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    token = f"[[doneness:{line_id}:{level}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_line_doneness(raw: str | None, line_id: str) -> str | None:
    wanted = str(line_id).lower()
    text = DONENESS_RE.sub(
        lambda match: "" if match.group(1).lower() == wanted else match.group(0),
        raw or "",
    ).strip()
    return text or None


def _strip_packed_tokens(raw: str | None) -> str:
    return ARRIVED_RE.sub("", WAIT_RE.sub("", RECEIPT_RE.sub("", BILL_RE.sub("", HANDOFF_RE.sub("", ALLERGEN_RE.sub("", DONENESS_RE.sub("", BAY_RE.sub("", VEHICLE_RE.sub("", SOURCE_RE.sub("", DIET_RE.sub("", HIGHCHAIR_RE.sub("", PACK_RE.sub("", FIRE_RE.sub("", SPICE_RE.sub("", OCCASION_RE.sub("", EMAIL_RE.sub("", CUTLERY_RE.sub("", PAGER_RE.sub("", SEAT_RE.sub("", HOLD_RE.sub("", ITEM_NOTE_RE.sub("", RUSH_RE.sub("", READY_RE.sub("", PHONE_RE.sub("", ALLERGY_RE.sub("", COVERS_RE.sub("", CHANNEL_RE.sub("", ZONE_RE.sub("", _strip_course_tokens(raw)))))))))))))))))))))))))))))).strip()


def _kept_tokens(raw: str | None) -> list[str]:
    text = raw or ""
    return (
        _course_tokens(text)
        + [match.group(0) for match in ITEM_NOTE_RE.finditer(text)]
        + [match.group(0) for match in HOLD_RE.finditer(text)]
        + [match.group(0) for match in SEAT_RE.finditer(text)]
        + [match.group(0) for match in SPICE_RE.finditer(text)]
        + [match.group(0) for match in DONENESS_RE.finditer(text)]
        + [match.group(0) for match in ZONE_RE.finditer(text)]
        + [match.group(0) for match in CHANNEL_RE.finditer(text)]
        + [match.group(0) for match in COVERS_RE.finditer(text)]
        + [match.group(0) for match in ALLERGY_RE.finditer(text)]
        + [match.group(0) for match in ALLERGEN_RE.finditer(text)]
        + [match.group(0) for match in OCCASION_RE.finditer(text)]
        + [match.group(0) for match in PHONE_RE.finditer(text)]
        + [match.group(0) for match in PAGER_RE.finditer(text)]
        + [match.group(0) for match in READY_RE.finditer(text)]
        + [match.group(0) for match in WAIT_RE.finditer(text)]
        + [match.group(0) for match in FIRE_RE.finditer(text)]
        + [match.group(0) for match in PACK_RE.finditer(text)]
        + [match.group(0) for match in RUSH_RE.finditer(text)]
        + [match.group(0) for match in BILL_RE.finditer(text)]
        + [match.group(0) for match in ARRIVED_RE.finditer(text)]
        + [match.group(0) for match in CUTLERY_RE.finditer(text)]
        + [match.group(0) for match in HIGHCHAIR_RE.finditer(text)]
        + [match.group(0) for match in DIET_RE.finditer(text)]
        + [match.group(0) for match in SOURCE_RE.finditer(text)]
        + [match.group(0) for match in VEHICLE_RE.finditer(text)]
        + [match.group(0) for match in BAY_RE.finditer(text)]
        + [match.group(0) for match in HANDOFF_RE.finditer(text)]
        + [match.group(0) for match in EMAIL_RE.finditer(text)]
        + [match.group(0) for match in RECEIPT_RE.finditer(text)]
    )


def pack_order_notes(
    *,
    delivery_address: str | None,
    notes: str | None,
    course_source: str | None = None,
) -> str | None:
    address = (delivery_address or "").strip()
    kitchen = _strip_packed_tokens(notes)
    parts = []
    if address:
        parts.append(f"{DELIVER_PREFIX}{address}{DELIVER_SUFFIX}")
    if kitchen:
        parts.append(kitchen)
    tokens = _kept_tokens(course_source)
    if tokens:
        parts.extend(tokens)
    return "\n".join(parts) or None


def unpack_order_notes(raw: str | None) -> tuple[str | None, str | None]:
    text = raw or ""
    start = text.find(DELIVER_PREFIX)
    if start < 0:
        kitchen = _strip_packed_tokens(text) or None
        return None, kitchen
    end = text.find(DELIVER_SUFFIX, start)
    if end < 0:
        kitchen = _strip_packed_tokens(text) or None
        return None, kitchen
    address = text[start + len(DELIVER_PREFIX) : end].strip() or None
    rest = f"{text[:start]}{text[end + len(DELIVER_SUFFIX):]}"
    kitchen = _strip_packed_tokens(rest) or None
    return address, kitchen


def zone_for_order(raw: str | None) -> str | None:
    match = ZONE_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1).strip() or None


def write_order_zone(raw: str | None, name: str) -> str | None:
    without = ZONE_RE.sub("", raw or "").strip()
    token = f"[[zone:{name}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_zone(raw: str | None) -> str | None:
    text = ZONE_RE.sub("", raw or "").strip()
    return text or None


def covers_for_order(raw: str | None) -> int | None:
    match = COVERS_RE.search(raw or "")
    if match is None:
        return None
    return int(match.group(1))


def write_order_covers(raw: str | None, count: int) -> str | None:
    people = int(count)
    if people < 1 or people > 40:
        raise HTTPException(status_code=422, detail="Covers must be from 1 to 40.")
    without = COVERS_RE.sub("", raw or "").strip()
    token = f"[[covers:{people}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_covers(raw: str | None) -> str | None:
    text = COVERS_RE.sub("", raw or "").strip()
    return text or None


def clean_allergy(value: str) -> str:
    text = str(value or "").strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not any(ch.isalnum() for ch in text)
    ):
        raise HTTPException(status_code=422, detail="Allergy must be a plain note.")
    return text


def allergy_for_order(raw: str | None) -> str | None:
    match = ALLERGY_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1).strip() or None


def write_order_allergy(raw: str | None, note: str) -> str | None:
    text = clean_allergy(note)
    without = ALLERGY_RE.sub("", raw or "").strip()
    token = f"[[allergy:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_allergy(raw: str | None) -> str | None:
    text = ALLERGY_RE.sub("", raw or "").strip()
    return text or None


def clean_occasion(value: str) -> str:
    text = str(value or "").strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not any(ch.isalnum() for ch in text)
    ):
        raise HTTPException(status_code=422, detail="Occasion must be a plain note.")
    return text


def occasion_for_order(raw: str | None) -> str | None:
    match = OCCASION_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1).strip() or None


def write_order_occasion(raw: str | None, note: str) -> str | None:
    text = clean_occasion(note)
    without = OCCASION_RE.sub("", raw or "").strip()
    token = f"[[occasion:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_occasion(raw: str | None) -> str | None:
    text = OCCASION_RE.sub("", raw or "").strip()
    return text or None


def clean_phone(value: str) -> str:
    cleaned = re.sub(r"[^\d+]", "", str(value or "").strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    digits = re.sub(r"\D", "", cleaned)
    if not cleaned.startswith("+") or len(digits) < 8 or len(digits) > 15:
        raise HTTPException(status_code=422, detail="Phone must be a full number.")
    return "+" + digits


def phone_for_order(raw: str | None) -> str | None:
    match = PHONE_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_phone(raw: str | None, phone: str) -> str | None:
    text = clean_phone(phone)
    without = PHONE_RE.sub("", raw or "").strip()
    token = f"[[phone:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_phone(raw: str | None) -> str | None:
    text = PHONE_RE.sub("", raw or "").strip()
    return text or None


def clean_pager(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Pager must be a pager number.") from None
    if isinstance(value, bool) or number < 1 or number > 999:
        raise HTTPException(status_code=422, detail="Pager must be a pager number.")
    return number


def pager_for_order(raw: str | None) -> int | None:
    match = PAGER_RE.search(raw or "")
    if match is None:
        return None
    return int(match.group(1))


def write_order_pager(raw: str | None, pager) -> str | None:
    number = clean_pager(pager)
    without = PAGER_RE.sub("", raw or "").strip()
    token = f"[[pager:{number}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_pager(raw: str | None) -> str | None:
    text = PAGER_RE.sub("", raw or "").strip()
    return text or None


def clean_ready_by(value: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
        raise HTTPException(status_code=422, detail="Ready by must be a clock time.")
    return text


def ready_by_for_order(raw: str | None) -> str | None:
    match = READY_RE.search(raw or "")
    if match is None:
        return None
    return f"{match.group(1)}:{match.group(2)}"


def write_order_ready_by(raw: str | None, when: str) -> str | None:
    text = clean_ready_by(when)
    without = READY_RE.sub("", raw or "").strip()
    token = f"[[ready:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_ready_by(raw: str | None) -> str | None:
    text = READY_RE.sub("", raw or "").strip()
    return text or None


def clean_quoted_wait(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Quoted wait must be from 5 to 180 minutes.") from None
    if isinstance(value, bool) or number < 5 or number > 180:
        raise HTTPException(status_code=422, detail="Quoted wait must be from 5 to 180 minutes.")
    return number


def quoted_wait_for_order(raw: str | None) -> int | None:
    match = WAIT_RE.search(raw or "")
    if match is None:
        return None
    return int(match.group(1))


def write_order_quoted_wait(raw: str | None, minutes) -> str | None:
    number = clean_quoted_wait(minutes)
    without = WAIT_RE.sub("", raw or "").strip()
    token = f"[[wait:{number}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_quoted_wait(raw: str | None) -> str | None:
    text = WAIT_RE.sub("", raw or "").strip()
    return text or None


def clean_fire_at(value: str) -> str:
    text = str(value or "").strip()
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", text):
        raise HTTPException(status_code=422, detail="Fire at must be a clock time.")
    return text


def fire_at_for_order(raw: str | None) -> str | None:
    match = FIRE_RE.search(raw or "")
    if match is None:
        return None
    return f"{match.group(1)}:{match.group(2)}"


def write_order_fire_at(raw: str | None, when: str) -> str | None:
    text = clean_fire_at(when)
    without = FIRE_RE.sub("", raw or "").strip()
    token = f"[[fire:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_fire_at(raw: str | None) -> str | None:
    text = FIRE_RE.sub("", raw or "").strip()
    return text or None


def clean_packaging(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Packaging must be a bag or a box.")
    text = str(value).strip().lower()
    if text not in PACKAGING:
        raise HTTPException(status_code=422, detail="Packaging must be a bag or a box.")
    return text


def packaging_for_order(raw: str | None) -> str | None:
    match = PACK_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_packaging(raw: str | None, kind) -> str | None:
    text = clean_packaging(kind)
    without = PACK_RE.sub("", raw or "").strip()
    token = f"[[pack:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_packaging(raw: str | None) -> str | None:
    text = PACK_RE.sub("", raw or "").strip()
    return text or None


def rush_for_order(raw: str | None) -> bool:
    return RUSH_RE.search(raw or "") is not None


def write_order_rush(raw: str | None) -> str:
    without = RUSH_RE.sub("", raw or "").strip()
    return f"{without}\n{RUSH_TOKEN}".strip() if without else RUSH_TOKEN


def drop_order_rush(raw: str | None) -> str | None:
    text = RUSH_RE.sub("", raw or "").strip()
    return text or None


def bill_asked_for_order(raw: str | None) -> bool:
    return BILL_RE.search(raw or "") is not None


def write_order_bill(raw: str | None) -> str:
    without = BILL_RE.sub("", raw or "").strip()
    return f"{without}\n{BILL_TOKEN}".strip() if without else BILL_TOKEN


def drop_order_bill(raw: str | None) -> str | None:
    text = BILL_RE.sub("", raw or "").strip()
    return text or None


def guest_arrived_for_order(raw: str | None) -> bool:
    return ARRIVED_RE.search(raw or "") is not None


def write_order_arrived(raw: str | None) -> str:
    without = ARRIVED_RE.sub("", raw or "").strip()
    return f"{without}\n{ARRIVED_TOKEN}".strip() if without else ARRIVED_TOKEN


def drop_order_arrived(raw: str | None) -> str | None:
    text = ARRIVED_RE.sub("", raw or "").strip()
    return text or None


def clean_receipt(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Receipt must be print, email, or declined.")
    text = str(value).strip().lower()
    if text not in RECEIPTS:
        raise HTTPException(status_code=422, detail="Receipt must be print, email, or declined.")
    return text


def receipt_for_order(raw: str | None) -> str | None:
    match = RECEIPT_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_receipt(raw: str | None, receipt) -> str | None:
    text = clean_receipt(receipt)
    without = RECEIPT_RE.sub("", raw or "").strip()
    token = f"[[receipt:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_receipt(raw: str | None) -> str | None:
    text = RECEIPT_RE.sub("", raw or "").strip()
    return text or None


def cutlery_for_order(raw: str | None) -> bool:
    return CUTLERY_RE.search(raw or "") is not None


def write_order_cutlery(raw: str | None) -> str:
    without = CUTLERY_RE.sub("", raw or "").strip()
    return f"{without}\n{CUTLERY_TOKEN}".strip() if without else CUTLERY_TOKEN


def drop_order_cutlery(raw: str | None) -> str | None:
    text = CUTLERY_RE.sub("", raw or "").strip()
    return text or None


def high_chair_for_order(raw: str | None) -> bool:
    return HIGHCHAIR_RE.search(raw or "") is not None


def write_order_high_chair(raw: str | None) -> str:
    without = HIGHCHAIR_RE.sub("", raw or "").strip()
    return f"{without}\n{HIGHCHAIR_TOKEN}".strip() if without else HIGHCHAIR_TOKEN


def drop_order_high_chair(raw: str | None) -> str | None:
    text = HIGHCHAIR_RE.sub("", raw or "").strip()
    return text or None


def clean_diet(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Diet must be vegetarian, vegan, or halal.")
    text = str(value).strip().lower()
    if text not in DIETS:
        raise HTTPException(status_code=422, detail="Diet must be vegetarian, vegan, or halal.")
    return text


def diet_for_order(raw: str | None) -> str | None:
    match = DIET_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_diet(raw: str | None, diet) -> str | None:
    text = clean_diet(diet)
    without = DIET_RE.sub("", raw or "").strip()
    token = f"[[diet:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_diet(raw: str | None) -> str | None:
    text = DIET_RE.sub("", raw or "").strip()
    return text or None


def clean_allergen(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Allergen must be nuts, gluten, dairy, or shellfish.")
    text = str(value).strip().lower()
    if text not in ALLERGENS:
        raise HTTPException(status_code=422, detail="Allergen must be nuts, gluten, dairy, or shellfish.")
    return text


def allergen_for_order(raw: str | None) -> str | None:
    match = ALLERGEN_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_allergen(raw: str | None, allergen) -> str | None:
    text = clean_allergen(allergen)
    without = ALLERGEN_RE.sub("", raw or "").strip()
    token = f"[[allergen:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_allergen(raw: str | None) -> str | None:
    text = ALLERGEN_RE.sub("", raw or "").strip()
    return text or None


def clean_guest_source(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Source must be walk-in, phone, or booking.")
    text = str(value).strip().lower()
    if text not in SOURCES:
        raise HTTPException(status_code=422, detail="Source must be walk-in, phone, or booking.")
    return text


def guest_source_for_order(raw: str | None) -> str | None:
    match = SOURCE_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_guest_source(raw: str | None, source) -> str | None:
    text = clean_guest_source(source)
    without = SOURCE_RE.sub("", raw or "").strip()
    token = f"[[source:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_guest_source(raw: str | None) -> str | None:
    text = SOURCE_RE.sub("", raw or "").strip()
    return text or None


def clean_vehicle(value: str) -> str:
    text = str(value or "").strip()
    if (
        len(text) < 2
        or len(text) > 80
        or "://" in text
        or "@" in text
        or "]" in text
        or "\n" in text
        or not any(ch.isalnum() for ch in text)
    ):
        raise HTTPException(status_code=422, detail="Vehicle must be a plain note.")
    return text


def vehicle_for_order(raw: str | None) -> str | None:
    match = VEHICLE_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1).strip() or None


def write_order_vehicle(raw: str | None, note: str) -> str | None:
    text = clean_vehicle(note)
    without = VEHICLE_RE.sub("", raw or "").strip()
    token = f"[[vehicle:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_vehicle(raw: str | None) -> str | None:
    text = VEHICLE_RE.sub("", raw or "").strip()
    return text or None


def clean_bay(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Bay must be a stall number from 1 to 40.") from None
    if isinstance(value, bool) or number < 1 or number > 40:
        raise HTTPException(status_code=422, detail="Bay must be a stall number from 1 to 40.")
    return number


def bay_for_order(raw: str | None) -> int | None:
    match = BAY_RE.search(raw or "")
    if match is None:
        return None
    return int(match.group(1))


def write_order_bay(raw: str | None, bay) -> str | None:
    number = clean_bay(bay)
    without = BAY_RE.sub("", raw or "").strip()
    token = f"[[bay:{number}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_bay(raw: str | None) -> str | None:
    text = BAY_RE.sub("", raw or "").strip()
    return text or None


def clean_handoff(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Handoff must be hand to the guest or leave at the door.")
    text = str(value).strip().lower()
    if text not in HANDOFFS:
        raise HTTPException(status_code=422, detail="Handoff must be hand to the guest or leave at the door.")
    return text


def handoff_for_order(raw: str | None) -> str | None:
    match = HANDOFF_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_handoff(raw: str | None, handoff) -> str | None:
    text = clean_handoff(handoff)
    without = HANDOFF_RE.sub("", raw or "").strip()
    token = f"[[handoff:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_handoff(raw: str | None) -> str | None:
    text = HANDOFF_RE.sub("", raw or "").strip()
    return text or None


def clean_guest_email(value: str) -> str:
    text = str(value or "").strip()
    domain = text.split("@", 1)[1] if text.count("@") == 1 else ""
    if (
        len(text) < 3
        or len(text) > 120
        or "://" in text
        or " " in text
        or "]" in text
        or "\n" in text
        or text.count("@") != 1
        or text.startswith("@")
        or text.endswith("@")
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
    ):
        raise HTTPException(status_code=422, detail="Email must be an email address.")
    return text


def guest_email_for_order(raw: str | None) -> str | None:
    match = EMAIL_RE.search(raw or "")
    if match is None:
        return None
    return match.group(1)


def write_order_guest_email(raw: str | None, email: str) -> str | None:
    text = clean_guest_email(email)
    without = EMAIL_RE.sub("", raw or "").strip()
    token = f"[[email:{text}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_order_guest_email(raw: str | None) -> str | None:
    text = EMAIL_RE.sub("", raw or "").strip()
    return text or None


def channel_for_order(raw: str | None) -> str | None:
    return "online" if CHANNEL_RE.search(raw or "") else None


def write_order_channel(raw: str | None) -> str:
    without = CHANNEL_RE.sub("", raw or "").strip()
    return f"{without}\n{CHANNEL_TOKEN}".strip() if without else CHANNEL_TOKEN


def clean_zone_name(value: str) -> str:
    text = str(value or "").strip()
    if (
        len(text) < 2
        or len(text) > 40
        or "://" in text
        or "@" in text
        or "]" in text
        or not any(ch.isalnum() for ch in text)
    ):
        raise HTTPException(status_code=422, detail="Delivery zone must be a place name.")
    return text


def _stored_zone_names(tenant: m.Tenant) -> list[str]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return []
    names = raw.get(ZONES_KEY) or []
    if not isinstance(names, list):
        return []
    return [str(name) for name in names if str(name).strip()]


async def list_delivery_zones(db: AsyncSession, tenant_id: str) -> list[str]:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    return _stored_zone_names(tenant)


async def replace_delivery_zones(db: AsyncSession, tenant_id: str, names: list[str]) -> list[str]:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    if len(names) > 20:
        raise HTTPException(status_code=422, detail="Keep 20 delivery zones or fewer.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for name in names:
        text = clean_zone_name(name)
        key = text.casefold()
        if key in seen:
            raise HTTPException(status_code=422, detail="Delivery zone is already on the list.")
        seen.add(key)
        cleaned.append(text)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    if cleaned:
        data[ZONES_KEY] = cleaned
    else:
        data.pop(ZONES_KEY, None)
    tenant.document_numbering = data
    await db.flush()
    return cleaned


async def match_delivery_zone(db: AsyncSession, tenant_id: str, zone: str | None) -> str | None:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    catalog = _stored_zone_names(tenant)
    text = (zone or "").strip()
    if not catalog:
        if text:
            raise HTTPException(status_code=422, detail="Add that delivery zone first.")
        return None
    if not text:
        raise HTTPException(status_code=422, detail="Choose a delivery zone.")
    for name in catalog:
        if name.casefold() == text.casefold():
            return name
    raise HTTPException(status_code=422, detail="Delivery zone is not on the list.")


def _online_orders_open(tenant: m.Tenant) -> bool:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return False
    return raw.get(ONLINE_KEY) is True


async def online_order_desk(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    return _serialize_online_orders(tenant)


async def set_online_orders(db: AsyncSession, tenant_id: str, *, open_orders: bool) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    if open_orders:
        data[ONLINE_KEY] = True
    else:
        data.pop(ONLINE_KEY, None)
    tenant.document_numbering = data
    await db.flush()
    return _serialize_online_orders(tenant)


def _serialize_online_orders(tenant: m.Tenant) -> dict:
    from app.config import settings

    path = f"/order/{tenant.slug}"
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    open_orders = _online_orders_open(tenant)
    qr = None
    if open_orders:
        import base64

        from app.barcodes import render_qr_png

        png = render_qr_png(f"{base}{path}")
        qr = "data:image/png;base64," + base64.b64encode(png).decode("ascii")
    return {
        "open": open_orders,
        "path": path,
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "order_url": f"{base}{path}",
        "qr": qr,
    }


async def _is_public_menu_item(db: AsyncSession, tenant_id: str, product: m.Product) -> bool:
    if not getattr(product, "is_active", True):
        return False
    station = (getattr(product, "prep_station", None) or "").strip().lower()
    recipe_menu = await _recipe_menu_id(db, tenant_id, product.id)
    if station not in {"kitchen", "bar"} and recipe_menu is None:
        return False
    if await _recipe_ingredient_id(db, tenant_id, product.id) and recipe_menu is None and station not in {"kitchen", "bar"}:
        return False
    return True


async def list_public_menu(db: AsyncSession, tenant_id: str) -> list[dict]:
    tenant = await db.get(m.Tenant, tenant_id)
    sold_out = set(_stored_sold_out(tenant))
    products = list(
        (
            await db.execute(
                select(m.Product).where(m.Product.tenant_id == tenant_id, m.Product.is_active.is_(True))
            )
        ).scalars()
    )
    rows = []
    for product in products:
        if not await _is_public_menu_item(db, tenant_id, product):
            continue
        if product.id in sold_out:
            continue
        rows.append(
            {
                "id": product.id,
                "name": product.name,
                "price": money_json(product.selling_price or 0),
            }
        )
    rows.sort(key=lambda row: str(row["name"]).casefold())
    return rows


def _stored_floor_places(tenant: m.Tenant) -> list[dict]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return []
    places = raw.get(FLOOR_KEY) or []
    if not isinstance(places, list):
        return []
    kept = []
    for place in places:
        if not isinstance(place, dict):
            continue
        table_id = str(place.get("table_id") or "").strip()
        if not table_id:
            continue
        kept.append({"table_id": table_id, "x": int(place.get("x") or 0), "y": int(place.get("y") or 0)})
    return kept


async def list_floor_places(db: AsyncSession, tenant_id: str) -> list[dict]:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    active = set(
        (
            await db.execute(
                select(m.RestaurantTable.id).where(
                    m.RestaurantTable.tenant_id == tenant.id,
                    m.RestaurantTable.is_active.is_(True),
                )
            )
        ).scalars()
    )
    return [place for place in _stored_floor_places(tenant) if place["table_id"] in active]


async def replace_floor_places(db: AsyncSession, tenant_id: str, places: list) -> list[dict]:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    if len(places) > 40:
        raise HTTPException(status_code=422, detail="Keep 40 tables on the floor or fewer.")
    cleaned: list[dict] = []
    seen: set[str] = set()
    for place in places:
        table_id = str(place.table_id).strip()
        if table_id in seen:
            raise HTTPException(status_code=422, detail="Table is already on the floor.")
        x = int(place.x)
        y = int(place.y)
        if x < 0 or x > 100 or y < 0 or y > 100:
            raise HTTPException(status_code=422, detail="Place the table on the floor.")
        table = await db.get(m.RestaurantTable, table_id)
        if table is None or table.tenant_id != tenant.id or not table.is_active:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.id in seen:
            raise HTTPException(status_code=422, detail="Table is already on the floor.")
        seen.add(table.id)
        cleaned.append({"table_id": table.id, "x": x, "y": y})
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    if cleaned:
        data[FLOOR_KEY] = cleaned
    else:
        data.pop(FLOOR_KEY, None)
    tenant.document_numbering = data
    await db.flush()
    return cleaned


def _kitchen_sound_on(tenant: m.Tenant) -> bool:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return False
    return raw.get(SOUND_KEY) is True


async def kitchen_sound(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    return {"on": _kitchen_sound_on(tenant)}


async def set_kitchen_sound(db: AsyncSession, tenant_id: str, *, on: bool) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    if on:
        data[SOUND_KEY] = True
    else:
        data.pop(SOUND_KEY, None)
    tenant.document_numbering = data
    await db.flush()
    return {"on": on}


def _stored_clock(tenant: m.Tenant) -> list[dict]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return []
    rows = raw.get(CLOCK_KEY) or []
    if not isinstance(rows, list):
        return []
    kept = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id") or not row.get("user_id"):
            continue
        kept.append(
            {
                "id": str(row["id"]),
                "user_id": str(row["user_id"]),
                "name": str(row.get("name") or "Staff"),
                "in_at": str(row.get("in_at") or ""),
                "out_at": str(row["out_at"]) if row.get("out_at") else None,
            }
        )
    return kept


def _trim_clock(rows: list[dict]) -> list[dict]:
    kept = list(rows)
    while len(kept) > 40:
        closed_index = next((index for index, row in enumerate(kept) if row.get("out_at")), None)
        if closed_index is None:
            raise HTTPException(status_code=422, detail="Too many people are clocked in.")
        kept.pop(closed_index)
    return kept


def _clock_body(rows: list[dict], user_id: str) -> dict:
    open_rows = [row for row in rows if not row.get("out_at")]
    return {
        "open": open_rows,
        "mine_open": any(row["user_id"] == user_id for row in open_rows),
    }


async def list_clock(db: AsyncSession, tenant_id: str, user_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    return _clock_body(_stored_clock(tenant), user_id)


async def _clock_user(db: AsyncSession, tenant_id: str, user_id: str) -> m.User:
    user = await db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id or not user.is_active:
        raise HTTPException(status_code=404, detail="Staff member not found")
    return user


async def clock_in(db: AsyncSession, tenant_id: str, user_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    user = await _clock_user(db, tenant_id, user_id)
    rows = _stored_clock(tenant)
    if any(row["user_id"] == user.id and not row.get("out_at") for row in rows):
        raise HTTPException(status_code=409, detail="Already clocked in.")
    name = (user.full_name or "").strip() or "Staff"
    rows.append(
        {
            "id": uid(),
            "user_id": user.id,
            "name": name,
            "in_at": _now().isoformat(timespec="seconds"),
            "out_at": None,
        }
    )
    rows = _trim_clock(rows)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    data[CLOCK_KEY] = rows
    tenant.document_numbering = data
    await db.flush()
    return _clock_body(rows, user.id)


async def clock_out(db: AsyncSession, tenant_id: str, user_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    user = await _clock_user(db, tenant_id, user_id)
    rows = _stored_clock(tenant)
    open_row = next((row for row in rows if row["user_id"] == user.id and not row.get("out_at")), None)
    if open_row is None:
        raise HTTPException(status_code=409, detail="Not clocked in.")
    open_row["out_at"] = _now().isoformat(timespec="seconds")
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    data[CLOCK_KEY] = rows
    tenant.document_numbering = data
    await db.flush()
    return _clock_body(rows, user.id)


def _stored_sold_out(tenant: m.Tenant | None) -> list[str]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return []
    rows = raw.get(SOLD_OUT_KEY) or []
    if not isinstance(rows, list):
        return []
    kept: list[str] = []
    seen: set[str] = set()
    for row in rows:
        product_id = str(row or "").strip()
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        kept.append(product_id)
    return kept


async def list_sold_out(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    items = []
    for product_id in _stored_sold_out(tenant):
        product = await db.get(m.Product, product_id)
        if product is None or product.tenant_id != tenant.id or not product.is_active:
            continue
        if not await _is_public_menu_item(db, tenant.id, product):
            continue
        items.append({"id": product.id, "name": product.name})
    return {"items": items}


async def replace_sold_out(db: AsyncSession, tenant_id: str, product_ids: list[str]) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    if len(product_ids) > 40:
        raise HTTPException(status_code=422, detail="Keep 40 sold-out items or fewer.")
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw_id in product_ids:
        product_id = str(raw_id).strip()
        if product_id in seen:
            raise HTTPException(status_code=422, detail="That item is already sold out.")
        product = await _product(db, tenant.id, product_id)
        if not product.is_active or not await _is_public_menu_item(db, tenant.id, product):
            raise HTTPException(status_code=422, detail="Choose a menu item.")
        seen.add(product.id)
        cleaned.append(product.id)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    if cleaned:
        data[SOLD_OUT_KEY] = cleaned
    else:
        data.pop(SOLD_OUT_KEY, None)
    tenant.document_numbering = data
    await db.flush()
    return await list_sold_out(db, tenant.id)


OPEN_STATUSES = {"open", "sent", "preparing", "ready"}
PAYMENT_METHODS = {"cash", "card", "wallet", "mobile_money"}
BILL_CREDIT_DETAIL = "A restaurant bill cannot be put on credit. Choose cash, card, wallet, or Mobile Money."
TILL_SKIP_STATUSES = frozenset({"cancelled", "void", "voided", "draft"})


def _now() -> datetime:
    return datetime.utcnow()


async def _product(db: AsyncSession, tenant_id: str, product_id: str) -> m.Product:
    row = (
        await db.execute(
            select(m.Product).where(m.Product.id == product_id, m.Product.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return row


async def _recipe_menu_id(db: AsyncSession, tenant_id: str, product_id: str) -> str | None:
    return (
        await db.execute(
            select(m.RestaurantRecipe.id).where(
                m.RestaurantRecipe.tenant_id == tenant_id,
                m.RestaurantRecipe.product_id == product_id,
                m.RestaurantRecipe.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()


async def _recipe_ingredient_id(db: AsyncSession, tenant_id: str, product_id: str) -> str | None:
    return (
        await db.execute(
            select(m.RestaurantRecipeLine.id).where(
                m.RestaurantRecipeLine.tenant_id == tenant_id,
                m.RestaurantRecipeLine.ingredient_id == product_id,
            ).limit(1)
        )
    ).scalar_one_or_none()


async def _require_sellable_menu_item(db: AsyncSession, tenant_id: str, product: m.Product) -> None:
    station = (getattr(product, "prep_station", None) or "").strip().lower()
    if station in {"kitchen", "bar"}:
        return
    if await _recipe_menu_id(db, tenant_id, product.id):
        return
    if await _recipe_ingredient_id(db, tenant_id, product.id):
        raise HTTPException(status_code=422, detail="Choose a menu item.")


async def _require_waste_ingredient(db: AsyncSession, tenant_id: str, product: m.Product) -> None:
    if await _recipe_ingredient_id(db, tenant_id, product.id):
        return
    station = (getattr(product, "prep_station", None) or "").strip().lower()
    if station in {"kitchen", "bar"} or await _recipe_menu_id(db, tenant_id, product.id):
        raise HTTPException(status_code=422, detail="Choose an ingredient.")


async def _allowed_stores(db: AsyncSession, tenant_id: str, user_id: str | None) -> list[str] | None:
    if not user_id:
        return None
    return await assigned_store_ids(db, tenant_id=tenant_id, user_id=user_id)


def _store_clause(column, allowed: list[str] | None):
    if allowed is None:
        return None
    if not allowed:
        return sql_false()
    return column.in_(list(allowed))


async def _require_store_for_scoped_user(db, tenant_id: str, user_id: str | None, store_id: str | None) -> None:
    if store_id:
        await assert_store_access(db, tenant_id=tenant_id, user_id=user_id or "", store_id=store_id)
    allowed = await _allowed_stores(db, tenant_id, user_id)
    if allowed is not None and store_id not in set(allowed):
        raise HTTPException(status_code=403, detail="Store is outside your access")


async def _till_receipts_since(
    db: AsyncSession, tenant_id: str, user_id: str | None, start: datetime
) -> tuple[float, int]:
    """Completed restaurant-till receipts since start. Other industries add nothing."""
    from app.packages import canonicalize_industry

    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        return 0.0, 0
    stmt = (
        select(m.Transaction, m.PosSession)
        .outerjoin(m.PosSession, m.PosSession.id == m.Transaction.session_id)
        .where(
            m.Transaction.tenant_id == tenant_id,
            m.Transaction.tx_type == "pos_sale",
            m.Transaction.created_at >= start,
        )
    )
    scope = _store_clause(m.PosSession.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    total = 0.0
    count = 0
    for tx, _session in (await db.execute(stmt)).all():
        if str(tx.status or "").strip().lower() in TILL_SKIP_STATUSES:
            continue
        total = money_json(round(total + money_json(tx.total), 2))
        count += 1
    return float(total), count


def _posted_till_return_filters(
    tenant_id: str,
    *,
    start: datetime | None,
    end: datetime | None,
    inclusive_end: bool = False,
):
    when = func.coalesce(m.SalesReturn.posted_at, m.SalesReturn.created_at)
    filters = [
        m.SalesReturn.tenant_id == tenant_id,
        m.SalesReturn.status == "posted",
        m.SalesReturn.transaction_id.is_not(None),
        m.SalesReturn.sales_invoice_id.is_(None),
    ]
    if start is not None:
        filters.append(when >= start)
    if end is not None:
        filters.append(when <= end if inclusive_end else when < end)
    return filters


async def _restaurant_company(db: AsyncSession, tenant_id: str) -> bool:
    from app.packages import canonicalize_industry

    tenant = await db.get(m.Tenant, tenant_id)
    return tenant is not None and canonicalize_industry(getattr(tenant, "industry", None)) == "restaurant"


def _scope_till_returns_by_sale_store(stmt, store_id: str | None, store_ids: list[str] | None):
    """A store filter follows the original receipt. A return with no store stays off that filter."""
    from app.reports import apply_store_scope

    if store_id is None and store_ids is None:
        return stmt
    stmt = stmt.outerjoin(m.Transaction, m.Transaction.id == m.SalesReturn.transaction_id).outerjoin(
        m.PosSession, m.PosSession.id == m.Transaction.session_id
    )
    return apply_store_scope(stmt, m.PosSession.store_id, store_id, store_ids)


async def posted_till_return_total(
    db: AsyncSession,
    tenant_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    inclusive_end: bool = False,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
    user_id: str | None = None,
) -> float:
    """Posted restaurant-till returns. Other industries add nothing. The receipt stays on the till list."""

    if not await _restaurant_company(db, tenant_id):
        return 0.0
    stmt = select(func.coalesce(func.sum(m.SalesReturn.total_amount), 0)).where(
        *_posted_till_return_filters(tenant_id, start=start, end=end, inclusive_end=inclusive_end)
    )
    if user_id is not None:
        allowed = await _allowed_stores(db, tenant_id, user_id)
        if allowed is not None:
            stmt = _scope_till_returns_by_sale_store(stmt, None, allowed)
    else:
        stmt = _scope_till_returns_by_sale_store(stmt, store_id, store_ids)
    return money_json((await db.execute(stmt)).scalar_one() or 0)


async def posted_till_returns(
    db: AsyncSession,
    tenant_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    inclusive_end: bool = False,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> list[m.SalesReturn]:
    """Posted restaurant-till returns in a window. Other industries get none."""

    if not await _restaurant_company(db, tenant_id):
        return []
    when = func.coalesce(m.SalesReturn.posted_at, m.SalesReturn.created_at)
    stmt = (
        select(m.SalesReturn)
        .where(*_posted_till_return_filters(tenant_id, start=start, end=end, inclusive_end=inclusive_end))
        .order_by(when.desc())
    )
    stmt = _scope_till_returns_by_sale_store(stmt, store_id, store_ids)
    return list((await db.execute(stmt)).scalars().all())


async def posted_till_return_moves(
    db: AsyncSession,
    tenant_id: str,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    inclusive_end: bool = False,
    store_id: str | None = None,
    store_ids: list[str] | None = None,
) -> list[dict]:
    """Returned restaurant-till dishes. Other industries get none. The receipt stays on the till list."""
    returns = await posted_till_returns(
        db,
        tenant_id,
        start=start,
        end=end,
        inclusive_end=inclusive_end,
        store_id=store_id,
        store_ids=store_ids,
    )
    if not returns:
        return []
    by_id = {row.id: row for row in returns}
    items = list(
        (
            await db.execute(
                select(m.SalesReturnItem).where(
                    m.SalesReturnItem.tenant_id == tenant_id,
                    m.SalesReturnItem.sales_return_id.in_(list(by_id)),
                )
            )
        ).scalars().all()
    )
    moves: list[dict] = []
    for item in items:
        ret = by_id.get(item.sales_return_id)
        if ret is None or not item.product_id:
            continue
        qty = money_json(item.quantity or 0)
        revenue = money_json(item.line_total or 0)
        if revenue == 0 and qty:
            revenue = money_json(round(money_json(item.unit_price or 0) * qty, 2))
        moves.append(
            {
                "transaction_id": ret.transaction_id,
                "return_number": ret.return_number,
                "when": ret.posted_at or ret.created_at,
                "product_id": item.product_id,
                "quantity": qty,
                "revenue": revenue,
                "cost": await sale_line_cost(db, tenant_id, item.product_id, qty),
            }
        )
    return moves


async def summary(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> dict:
    allowed = await _allowed_stores(db, tenant_id, user_id)
    order_scope = _store_clause(m.RestaurantOrder.store_id, allowed)
    table_scope = _store_clause(m.RestaurantTable.store_id, allowed)
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    # RestaurantOrder has no stored currency/exchange_rate; do not invent FX.
    sales_stmt = select(func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0)).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status == "completed",
        m.RestaurantOrder.completed_at >= start,
    )
    if order_scope is not None:
        sales_stmt = sales_stmt.where(order_scope)
    sales = (await db.execute(sales_stmt)).scalar_one()
    table_sales = money_json(sales)
    till_sales, till_count = await _till_receipts_since(db, tenant_id, user_id, start)
    till_returns = await posted_till_return_total(db, tenant_id, start=start, user_id=user_id)
    till_sales = money_json(round(till_sales - till_returns, 2))
    open_stmt = select(func.count()).select_from(m.RestaurantOrder).where(
        m.RestaurantOrder.tenant_id == tenant_id,
        m.RestaurantOrder.status.in_(tuple(OPEN_STATUSES)),
    )
    if order_scope is not None:
        open_stmt = open_stmt.where(order_scope)
    open_orders = (await db.execute(open_stmt)).scalar_one()
    table_stmt = (
        select(m.RestaurantTable.status, func.count())
        .where(m.RestaurantTable.tenant_id == tenant_id, m.RestaurantTable.is_active.is_(True))
        .group_by(m.RestaurantTable.status)
    )
    if table_scope is not None:
        table_stmt = table_stmt.where(table_scope)
    tables = (await db.execute(table_stmt)).all()
    kitchen_stmt = (
        select(m.RestaurantKitchenTicket.station, func.count())
        .select_from(m.RestaurantKitchenTicket)
        .join(m.RestaurantOrder, m.RestaurantOrder.id == m.RestaurantKitchenTicket.order_id)
        .where(
            m.RestaurantKitchenTicket.tenant_id == tenant_id,
            m.RestaurantKitchenTicket.status.in_(("queued", "preparing")),
        )
        .group_by(m.RestaurantKitchenTicket.station)
    )
    if order_scope is not None:
        kitchen_stmt = kitchen_stmt.where(order_scope)
    by_station = {
        (station or "kitchen"): int(count or 0)
        for station, count in (await db.execute(kitchen_stmt)).all()
    }
    kitchen_queue = int(by_station.get("kitchen", 0))
    bar_queue = int(by_station.get("bar", 0))
    low_stock = (
        await db.execute(
            select(func.count()).select_from(m.Product).where(
                m.Product.tenant_id == tenant_id,
                m.Product.is_active.is_(True),
                m.Product.reorder_level > 0,
                m.Product.stock_qty <= m.Product.reorder_level,
            )
        )
    ).scalar_one()
    booking_requests = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantBooking).where(
                m.RestaurantBooking.tenant_id == tenant_id,
                m.RestaurantBooking.status == "requested",
            )
        )
    ).scalar_one()
    return {
        "sales_today": money_json(round(table_sales + till_sales, 2)),
        "table_sales_today": table_sales,
        "till_sales_today": money_json(till_sales),
        "till_receipts": till_count,
        "open_orders": int(open_orders or 0),
        "tables": {status: int(count) for status, count in tables},
        "kitchen_backlog": kitchen_queue + bar_queue,
        "kitchen_queue": kitchen_queue,
        "bar_queue": bar_queue,
        "booking_requests": int(booking_requests or 0),
        "low_stock_ingredients": int(low_stock or 0),
    }


async def create_table(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.RestaurantTable:
    code = require_honest_narrative(payload.code, label="table code", min_length=1)[:40]
    name = require_honest_narrative(payload.name, label="table name", min_length=1)[:120]
    await _require_store_for_scoped_user(db, tenant_id, user_id, payload.store_id)
    row = m.RestaurantTable(
        tenant_id=tenant_id,
        store_id=payload.store_id,
        code=code,
        name=name,
        seats=max(1, int(payload.seats or 2)),
        status="available",
    )
    db.add(row)
    await db.flush()
    if getattr(payload, "room", None):
        await _write_table_room(db, tenant_id, row.id, payload.room)
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_table_created", entity="restaurant_table", entity_id=row.id,
        details={"code": code},
    )
    return row


async def _table_code_taken(
    db: AsyncSession, tenant_id: str, code: str, *, skip_id: str | None = None
) -> bool:
    stmt = select(m.RestaurantTable.id).where(
        m.RestaurantTable.tenant_id == tenant_id,
        m.RestaurantTable.code == code,
        m.RestaurantTable.is_active.is_(True),
    )
    if skip_id:
        stmt = stmt.where(m.RestaurantTable.id != skip_id)
    return (await db.execute(stmt.limit(1))).scalar_one_or_none() is not None


async def update_table(
    db: AsyncSession, tenant_id: str, table_id: str, payload, *, user_id: str | None
) -> m.RestaurantTable:
    table = await _table(db, tenant_id, table_id, user_id=user_id)
    if not table.is_active:
        raise HTTPException(status_code=409, detail="Table is retired.")
    if payload.code is not None:
        code = require_honest_narrative(payload.code, label="table code", min_length=1)[:40]
        if await _table_code_taken(db, tenant_id, code, skip_id=table.id):
            raise HTTPException(status_code=409, detail="Table code already exists.")
        table.code = code
    if payload.name is not None:
        table.name = require_honest_narrative(payload.name, label="table name", min_length=1)[:120]
    if payload.seats is not None:
        table.seats = max(1, int(payload.seats or 2))
    if "store_id" in getattr(payload, "model_fields_set", set()):
        raw = getattr(payload, "store_id", None)
        store_id = str(raw).strip() if raw else None
        if store_id:
            store = await db.get(m.Store, store_id)
            if store is None or store.tenant_id != tenant_id or not store.is_active:
                raise HTTPException(status_code=404, detail="Store not found")
            await _require_store_for_scoped_user(db, tenant_id, user_id, store.id)
            table.store_id = store.id
        else:
            await _require_store_for_scoped_user(db, tenant_id, user_id, None)
            table.store_id = None
    if "room" in getattr(payload, "model_fields_set", set()):
        await _write_table_room(db, tenant_id, table.id, payload.room)
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_table_updated",
        entity="restaurant_table",
        entity_id=table.id,
        details={"code": table.code, "seats": table.seats},
    )
    return table


async def retire_table(
    db: AsyncSession, tenant_id: str, table_id: str, *, user_id: str | None
) -> m.RestaurantTable:
    table = await _table(db, tenant_id, table_id, user_id=user_id)
    if not table.is_active:
        raise HTTPException(status_code=409, detail="Table is already retired.")
    if table.status != "available":
        raise HTTPException(status_code=409, detail="Finish the order or booking before retiring this table.")
    open_order = (
        await db.execute(
            select(m.RestaurantOrder.id).where(
                m.RestaurantOrder.tenant_id == tenant_id,
                m.RestaurantOrder.table_id == table.id,
                m.RestaurantOrder.status.notin_(("completed", "cancelled", "voided", "refunded")),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if open_order:
        raise HTTPException(status_code=409, detail="Finish the order or booking before retiring this table.")
    table.is_active = False
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_table_retired",
        entity="restaurant_table",
        entity_id=table.id,
        details={"code": table.code},
    )
    return table


async def list_tables(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[m.RestaurantTable]:
    stmt = select(m.RestaurantTable).where(
        m.RestaurantTable.tenant_id == tenant_id,
        m.RestaurantTable.is_active.is_(True),
    ).order_by(m.RestaurantTable.code)
    scope = _store_clause(m.RestaurantTable.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


def serialize_table(row: m.RestaurantTable, *, room: str | None = None) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "seats": row.seats,
        "status": row.status,
        "store_id": row.store_id,
        "is_active": row.is_active,
        "room": room,
    }


def _stored_rooms(tenant: m.Tenant | None) -> dict[str, str]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return {}
    rooms = raw.get(ROOM_KEY) or {}
    if not isinstance(rooms, dict):
        return {}
    kept: dict[str, str] = {}
    for key, value in rooms.items():
        table_id = str(key or "").strip()
        text = str(value or "").strip().lower()
        if table_id and text in ROOMS:
            kept[table_id] = text
    return kept


def clean_room(value) -> str:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Room must be dining, patio, or private.")
    text = str(value).strip().lower()
    if text not in ROOMS:
        raise HTTPException(status_code=422, detail="Room must be dining, patio, or private.")
    return text


async def table_rooms(db: AsyncSession, tenant_id: str) -> dict[str, str]:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    return _stored_rooms(tenant)


async def _write_table_room(db: AsyncSession, tenant_id: str, table_id: str, room: str | None) -> None:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    rooms = _stored_rooms(tenant)
    if room is None:
        rooms.pop(table_id, None)
    else:
        rooms[table_id] = clean_room(room)
    if rooms:
        data[ROOM_KEY] = rooms
    else:
        data.pop(ROOM_KEY, None)
    tenant.document_numbering = data
    await db.flush()


def _stored_cook_times(tenant: m.Tenant | None) -> dict[str, int]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return {}
    rows = raw.get(COOK_KEY) or {}
    if not isinstance(rows, dict):
        return {}
    kept: dict[str, int] = {}
    for key, value in rows.items():
        recipe_id = str(key or "").strip()
        if isinstance(value, bool) or not recipe_id:
            continue
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= minutes <= 180:
            kept[recipe_id] = minutes
    return kept


def clean_cook_time(value) -> int:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Cook time must be from 1 to 180 minutes.")
    try:
        minutes = int(str(value).strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Cook time must be from 1 to 180 minutes.")
    if minutes < 1 or minutes > 180:
        raise HTTPException(status_code=422, detail="Cook time must be from 1 to 180 minutes.")
    return minutes


async def _write_cook_time(db: AsyncSession, tenant_id: str, recipe_id: str, minutes: int | None) -> None:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    times = _stored_cook_times(tenant)
    if minutes is None:
        times.pop(recipe_id, None)
    else:
        times[recipe_id] = clean_cook_time(minutes)
    if times:
        data[COOK_KEY] = times
    else:
        data.pop(COOK_KEY, None)
    tenant.document_numbering = data
    await db.flush()


def _stored_servings(tenant: m.Tenant | None) -> dict[str, int]:
    raw = getattr(tenant, "document_numbering", None) or {}
    if not isinstance(raw, dict):
        return {}
    rows = raw.get(SERVINGS_KEY) or {}
    if not isinstance(rows, dict):
        return {}
    kept: dict[str, int] = {}
    for key, value in rows.items():
        recipe_id = str(key or "").strip()
        if isinstance(value, bool) or not recipe_id:
            continue
        try:
            count = int(value)
        except (TypeError, ValueError):
            continue
        if 1 <= count <= 40:
            kept[recipe_id] = count
    return kept


def clean_servings(value) -> int:
    if isinstance(value, bool) or value is None:
        raise HTTPException(status_code=422, detail="Servings must be from 1 to 40.")
    try:
        count = int(str(value).strip())
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Servings must be from 1 to 40.")
    if count < 1 or count > 40:
        raise HTTPException(status_code=422, detail="Servings must be from 1 to 40.")
    return count


async def _write_servings(db: AsyncSession, tenant_id: str, recipe_id: str, count: int | None) -> None:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    servings = _stored_servings(tenant)
    if count is None:
        servings.pop(recipe_id, None)
    else:
        servings[recipe_id] = clean_servings(count)
    if servings:
        data[SERVINGS_KEY] = servings
    else:
        data.pop(SERVINGS_KEY, None)
    tenant.document_numbering = data
    await db.flush()


async def _table(
    db: AsyncSession, tenant_id: str, table_id: str, *, user_id: str | None = None
) -> m.RestaurantTable:
    table = await db.get(m.RestaurantTable, table_id)
    if table is None or table.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Table not found")
    await _require_store_for_scoped_user(db, tenant_id, user_id, table.store_id)
    return table


async def hold_table(
    db: AsyncSession, tenant_id: str, table_id: str, *, user_id: str | None
) -> m.RestaurantTable:
    table = await _table(db, tenant_id, table_id, user_id=user_id)
    if not table.is_active:
        raise HTTPException(status_code=409, detail="Table is retired.")
    if table.status == "held":
        raise HTTPException(status_code=409, detail="Table is already held.")
    if table.status != "available":
        raise HTTPException(status_code=409, detail="Table has guests.")
    table.status = "held"
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_table_held",
        entity="restaurant_table",
        entity_id=table.id,
        details={"code": table.code},
    )
    return table


async def release_table(
    db: AsyncSession, tenant_id: str, table_id: str, *, user_id: str | None
) -> m.RestaurantTable:
    table = await _table(db, tenant_id, table_id, user_id=user_id)
    if not table.is_active:
        raise HTTPException(status_code=409, detail="Table is retired.")
    if table.status == "available":
        raise HTTPException(status_code=409, detail="Table is already free.")
    if table.status != "held":
        raise HTTPException(status_code=409, detail="Finish the order or booking before releasing this table.")
    table.status = "available"
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_table_released",
        entity="restaurant_table",
        entity_id=table.id,
        details={"code": table.code},
    )
    return table


async def list_modifier_groups(db: AsyncSession, tenant_id: str) -> list[dict]:
    groups = list(
        (
            await db.execute(
                select(m.RestaurantModifierGroup)
                .where(m.RestaurantModifierGroup.tenant_id == tenant_id, m.RestaurantModifierGroup.is_active.is_(True))
                .order_by(m.RestaurantModifierGroup.name)
            )
        ).scalars()
    )
    if not groups:
        return []
    group_ids = {row.id for row in groups}
    modifiers = list(
        (
            await db.execute(
                select(m.RestaurantModifier).where(
                    m.RestaurantModifier.tenant_id == tenant_id,
                    m.RestaurantModifier.group_id.in_(group_ids),
                    m.RestaurantModifier.is_active.is_(True),
                )
            )
        ).scalars()
    )
    return [
        {
            "id": group.id,
            "name": group.name,
            "modifiers": [
                {"id": row.id, "name": row.name, "price": money_json(row.price or 0)}
                for row in modifiers
                if row.group_id == group.id
            ],
        }
        for group in groups
    ]


async def create_modifier_group(db: AsyncSession, tenant_id: str, name: str) -> m.RestaurantModifierGroup:
    row = m.RestaurantModifierGroup(
        tenant_id=tenant_id,
        name=require_honest_narrative(name, label="modifier group", min_length=1)[:120],
    )
    db.add(row)
    await db.flush()
    return row


async def update_modifier_group(
    db: AsyncSession, tenant_id: str, group_id: str, payload, *, user_id: str | None
) -> m.RestaurantModifierGroup:
    row = await db.get(m.RestaurantModifierGroup, group_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Extra group not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Retired extra groups cannot be changed.")
    changed = False
    if payload.name is not None:
        row.name = require_honest_narrative(payload.name, label="modifier group", min_length=1)[:120]
        changed = True
    if not changed:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_extra_group_updated",
        entity="restaurant_modifier_group",
        entity_id=row.id,
        details={"name": row.name},
    )
    return row


async def retire_modifier_group(
    db: AsyncSession, tenant_id: str, group_id: str, *, user_id: str | None
) -> m.RestaurantModifierGroup:
    row = await db.get(m.RestaurantModifierGroup, group_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Extra group not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Extra group is already retired.")
    leftover = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantModifier).where(
                m.RestaurantModifier.tenant_id == tenant_id,
                m.RestaurantModifier.group_id == row.id,
                m.RestaurantModifier.is_active.is_(True),
            )
        )
    ).scalar_one()
    if leftover:
        raise HTTPException(status_code=409, detail="Retire leftover extras first.")
    row.is_active = False
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_extra_group_retired",
        entity="restaurant_modifier_group",
        entity_id=row.id,
        details={"name": row.name},
    )
    return row


async def add_modifier(db: AsyncSession, tenant_id: str, group_id: str, *, name: str, price) -> m.RestaurantModifier:
    group = await db.get(m.RestaurantModifierGroup, group_id)
    if group is None or group.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Modifier group not found")
    if not group.is_active:
        raise HTTPException(status_code=409, detail="Retired extra groups cannot take extras.")
    row = m.RestaurantModifier(
        tenant_id=tenant_id,
        group_id=group.id,
        name=require_honest_narrative(name, label="modifier name", min_length=1)[:120],
        price=money_json(price or 0),
    )
    db.add(row)
    await db.flush()
    return row


async def update_modifier(
    db: AsyncSession, tenant_id: str, modifier_id: str, payload, *, user_id: str | None
) -> m.RestaurantModifier:
    row = await db.get(m.RestaurantModifier, modifier_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Extra not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Retired extras cannot be changed.")
    changed = False
    if payload.name is not None:
        row.name = require_honest_narrative(payload.name, label="modifier name", min_length=1)[:120]
        changed = True
    if payload.price is not None:
        row.price = money_json(payload.price)
        changed = True
    if not changed:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_extra_updated",
        entity="restaurant_modifier",
        entity_id=row.id,
        details={"name": row.name, "price": money_json(row.price or 0)},
    )
    return row


async def retire_modifier(
    db: AsyncSession, tenant_id: str, modifier_id: str, *, user_id: str | None
) -> m.RestaurantModifier:
    row = await db.get(m.RestaurantModifier, modifier_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Extra not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Extra is already retired.")
    row.is_active = False
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_extra_retired",
        entity="restaurant_modifier",
        entity_id=row.id,
        details={"name": row.name},
    )
    return row


async def list_recipes(db: AsyncSession, tenant_id: str) -> list[dict]:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    cook_times = _stored_cook_times(tenant)
    servings = _stored_servings(tenant)
    recipes = list(
        (
            await db.execute(
                select(m.RestaurantRecipe)
                .where(m.RestaurantRecipe.tenant_id == tenant_id, m.RestaurantRecipe.is_active.is_(True))
                .order_by(m.RestaurantRecipe.name)
            )
        ).scalars()
    )
    if not recipes:
        return []
    recipe_ids = {row.id for row in recipes}
    lines = list(
        (
            await db.execute(
                select(m.RestaurantRecipeLine).where(
                    m.RestaurantRecipeLine.tenant_id == tenant_id,
                    m.RestaurantRecipeLine.recipe_id.in_(recipe_ids),
                )
            )
        ).scalars()
    )
    product_ids = {row.product_id for row in recipes} | {row.ingredient_id for row in lines}
    products = {}
    if product_ids:
        products = {
            row.id: row
            for row in (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == tenant_id,
                        m.Product.id.in_(product_ids),
                    )
                )
            ).scalars()
        }
    return [
        {
            "id": recipe.id,
            "name": recipe.name,
            "product_id": recipe.product_id,
            "menu_item": products[recipe.product_id].name if recipe.product_id in products else "Menu item",
            "station": (
                products[recipe.product_id].prep_station
                if recipe.product_id in products and (products[recipe.product_id].prep_station or "") in {"kitchen", "bar"}
                else "kitchen"
            ),
            "cook_time": cook_times.get(recipe.id),
            "servings": servings.get(recipe.id),
            "lines": [
                {
                    "ingredient_id": line.ingredient_id,
                    "name": products[line.ingredient_id].name if line.ingredient_id in products else "Ingredient",
                    "quantity": money_json(line.quantity),
                }
                for line in lines
                if line.recipe_id == recipe.id
            ],
        }
        for recipe in recipes
    ]


async def create_recipe(db: AsyncSession, tenant_id: str, payload) -> m.RestaurantRecipe:
    await _product(db, tenant_id, payload.product_id)
    existing = (
        await db.execute(
            select(m.RestaurantRecipe).where(
                m.RestaurantRecipe.tenant_id == tenant_id,
                m.RestaurantRecipe.product_id == payload.product_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Recipe already exists for this menu item")
    if not payload.lines:
        raise HTTPException(status_code=422, detail="Recipe needs at least one ingredient")
    recipe = m.RestaurantRecipe(
        tenant_id=tenant_id,
        product_id=payload.product_id,
        name=require_honest_narrative(payload.name, label="recipe name", min_length=1)[:160],
    )
    db.add(recipe)
    await db.flush()
    for line in payload.lines:
        await _product(db, tenant_id, line.ingredient_id)
        qty = money_json(line.quantity)
        if qty <= 0:
            raise HTTPException(status_code=422, detail="Ingredient quantity must be greater than zero")
        db.add(
            m.RestaurantRecipeLine(
                tenant_id=tenant_id,
                recipe_id=recipe.id,
                ingredient_id=line.ingredient_id,
                quantity=qty,
            )
        )
    await db.flush()
    if getattr(payload, "cook_time", None):
        await _write_cook_time(db, tenant_id, recipe.id, payload.cook_time)
    if getattr(payload, "servings", None):
        await _write_servings(db, tenant_id, recipe.id, payload.servings)
    return recipe


async def update_recipe(
    db: AsyncSession, tenant_id: str, recipe_id: str, payload, *, user_id: str | None
) -> m.RestaurantRecipe:
    row = await db.get(m.RestaurantRecipe, recipe_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Retired recipes cannot be changed.")
    changed = False
    if payload.name is not None:
        row.name = require_honest_narrative(payload.name, label="recipe name", min_length=1)[:160]
        changed = True
    if payload.lines is not None:
        if not payload.lines:
            raise HTTPException(status_code=422, detail="Recipe needs at least one ingredient")
        await db.execute(
            delete(m.RestaurantRecipeLine).where(
                m.RestaurantRecipeLine.tenant_id == tenant_id,
                m.RestaurantRecipeLine.recipe_id == row.id,
            )
        )
        for line in payload.lines:
            ingredient = await _product(db, tenant_id, line.ingredient_id)
            await _require_waste_ingredient(db, tenant_id, ingredient)
            qty = money_json(line.quantity)
            if qty <= 0:
                raise HTTPException(status_code=422, detail="Ingredient quantity must be greater than zero")
            db.add(
                m.RestaurantRecipeLine(
                    tenant_id=tenant_id,
                    recipe_id=row.id,
                    ingredient_id=ingredient.id,
                    quantity=qty,
                )
            )
        changed = True
    if "cook_time" in getattr(payload, "model_fields_set", set()):
        await _write_cook_time(db, tenant_id, row.id, payload.cook_time)
        changed = True
    if "servings" in getattr(payload, "model_fields_set", set()):
        await _write_servings(db, tenant_id, row.id, payload.servings)
        changed = True
    if not changed:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_recipe_updated",
        entity="restaurant_recipe",
        entity_id=row.id,
        details={"name": row.name},
    )
    return row


async def retire_recipe(
    db: AsyncSession, tenant_id: str, recipe_id: str, *, user_id: str | None
) -> m.RestaurantRecipe:
    row = await db.get(m.RestaurantRecipe, recipe_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if not row.is_active:
        raise HTTPException(status_code=409, detail="Recipe is already retired.")
    row.is_active = False
    await _write_cook_time(db, tenant_id, row.id, None)
    await _write_servings(db, tenant_id, row.id, None)
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_recipe_retired",
        entity="restaurant_recipe",
        entity_id=row.id,
        details={"name": row.name},
    )
    return row


async def _next_number(db: AsyncSession, tenant_id: str) -> str:
    count = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantOrder).where(m.RestaurantOrder.tenant_id == tenant_id)
        )
    ).scalar_one()
    return f"R-{int(count or 0) + 1:04d}"


async def create_order(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> m.RestaurantOrder:
    mode = (payload.service_mode or "").strip().lower()
    if mode not in SERVICE_MODES:
        raise HTTPException(status_code=422, detail="service_mode must be dine_in, takeaway, or delivery")
    method = (payload.payment_method or "cash").strip().lower()
    if method == "credit":
        raise HTTPException(status_code=422, detail=BILL_CREDIT_DETAIL)
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=422, detail="payment_method is not supported")
    await _require_store_for_scoped_user(db, tenant_id, user_id, payload.store_id)
    table_id = (payload.table_id or "").strip() or None
    if mode == "dine_in" and not table_id:
        has_table = (
            await db.execute(
                select(m.RestaurantTable.id).where(
                    m.RestaurantTable.tenant_id == tenant_id,
                    m.RestaurantTable.is_active.is_(True),
                ).limit(1)
            )
        ).scalar_one_or_none()
        if has_table:
            raise HTTPException(status_code=422, detail="Dine in needs a table.")
    if mode == "dine_in" and table_id:
        table = await db.get(m.RestaurantTable, table_id)
        if table is None or table.tenant_id != tenant_id or not table.is_active:
            raise HTTPException(status_code=404, detail="Table not found")
        table.status = "occupied"
    if not payload.lines:
        raise HTTPException(status_code=422, detail="Order needs at least one menu item")
    address = optional_honest_narrative(getattr(payload, "delivery_address", None), label="delivery address")
    if mode == "delivery" and not address:
        raise HTTPException(status_code=422, detail="Delivery needs an address")
    if mode != "delivery":
        address = None
    order = m.RestaurantOrder(
        tenant_id=tenant_id,
        store_id=payload.store_id,
        order_number=await _next_number(db, tenant_id),
        service_mode=mode,
        table_id=table_id if mode == "dine_in" else None,
        customer_name=optional_honest_narrative(payload.customer_name, label="customer name"),
        status="open",
        payment_method=method,
        notes=pack_order_notes(
            delivery_address=address,
            notes=optional_honest_narrative(payload.notes, label="order notes"),
        ),
        created_by=user_id,
    )
    if mode == "delivery":
        zone = await match_delivery_zone(db, tenant_id, getattr(payload, "delivery_zone", None))
        if zone:
            order.notes = write_order_zone(order.notes, zone)
    covers = getattr(payload, "covers", None)
    if covers is not None:
        order.notes = write_order_covers(order.notes, int(covers))
    allergy = getattr(payload, "allergy", None)
    if allergy:
        order.notes = write_order_allergy(order.notes, allergy)
    allergen = getattr(payload, "allergen", None)
    if allergen:
        order.notes = write_order_allergen(order.notes, allergen)
    occasion = getattr(payload, "occasion", None)
    if occasion:
        order.notes = write_order_occasion(order.notes, occasion)
    phone = getattr(payload, "phone", None)
    if phone:
        order.notes = write_order_phone(order.notes, phone)
    pager = getattr(payload, "pager", None)
    if pager is not None:
        order.notes = write_order_pager(order.notes, pager)
    ready_by = getattr(payload, "ready_by", None)
    if ready_by:
        order.notes = write_order_ready_by(order.notes, ready_by)
    quoted_wait = getattr(payload, "quoted_wait", None)
    if quoted_wait:
        order.notes = write_order_quoted_wait(order.notes, quoted_wait)
    fire_at = getattr(payload, "fire_at", None)
    if fire_at:
        order.notes = write_order_fire_at(order.notes, fire_at)
    packaging = getattr(payload, "packaging", None)
    if packaging:
        order.notes = write_order_packaging(order.notes, packaging)
    if getattr(payload, "rush", None) is True:
        order.notes = write_order_rush(order.notes)
    if getattr(payload, "bill_asked", None) is True:
        order.notes = write_order_bill(order.notes)
    if getattr(payload, "guest_arrived", None) is True:
        order.notes = write_order_arrived(order.notes)
    if getattr(payload, "cutlery", None) is True:
        order.notes = write_order_cutlery(order.notes)
    if getattr(payload, "high_chair", None) is True:
        order.notes = write_order_high_chair(order.notes)
    diet = getattr(payload, "diet", None)
    if diet:
        order.notes = write_order_diet(order.notes, diet)
    guest_source = getattr(payload, "guest_source", None)
    if guest_source:
        order.notes = write_order_guest_source(order.notes, guest_source)
    vehicle = getattr(payload, "vehicle", None)
    if vehicle:
        order.notes = write_order_vehicle(order.notes, vehicle)
    bay = getattr(payload, "bay", None)
    if bay:
        order.notes = write_order_bay(order.notes, bay)
    handoff = getattr(payload, "handoff", None)
    if handoff:
        order.notes = write_order_handoff(order.notes, handoff)
    guest_email = getattr(payload, "guest_email", None)
    if guest_email:
        order.notes = write_order_guest_email(order.notes, guest_email)
    receipt = getattr(payload, "receipt", None)
    if receipt:
        order.notes = write_order_receipt(order.notes, receipt)
    db.add(order)
    await db.flush()
    for line in payload.lines:
        row = await _add_order_line(db, tenant_id, order, line)
        course = getattr(line, "course", None)
        if course:
            order.notes = write_line_course(order.notes, row.id, str(course))
        item_note = getattr(line, "note", None)
        if item_note:
            order.notes = write_line_note(order.notes, row.id, str(item_note))
        if getattr(line, "hold", None) is True:
            order.notes = write_line_hold(order.notes, row.id)
        if getattr(line, "seat", None) is not None:
            order.notes = write_line_seat(order.notes, row.id, line.seat)
        if getattr(line, "spice", None):
            order.notes = write_line_spice(order.notes, row.id, line.spice)
        if getattr(line, "doneness", None):
            order.notes = write_line_doneness(order.notes, row.id, line.doneness)
    await _refresh_order_totals(db, order)
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_created", entity="restaurant_order", entity_id=order.id,
        details={"order_number": order.order_number, "total": money_json(order.total_amount)},
    )
    return order


async def _add_order_line(db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line) -> m.RestaurantOrderLine:
    product = await _product(db, tenant_id, line.product_id)
    await _require_sellable_menu_item(db, tenant_id, product)
    tenant = await db.get(m.Tenant, tenant_id)
    if product.id in set(_stored_sold_out(tenant)):
        raise HTTPException(status_code=422, detail="That item is sold out.")
    qty = money_json(line.quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Line quantity must be greater than zero")
    price = money_json(line.unit_price if line.unit_price is not None else product.selling_price or 0)
    extra = 0.0
    station = (product.prep_station or "kitchen") if (product.prep_station or "") in {"kitchen", "bar"} else "kitchen"
    line_id = uid()
    values = {
        "id": line_id,
        "tenant_id": tenant_id,
        "order_id": order.id,
        "product_id": product.id,
        "quantity": qty,
        "unit_price": price,
        "line_total": money_json(qty * price),
        "station": station,
    }
    if await _line_prep_status_live(db):
        values["prep_status"] = "queued"
    await db.execute(insert(m.RestaurantOrderLine.__table__).values(**values))
    await db.flush()
    row = await db.get(m.RestaurantOrderLine, line_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Order line was not saved")
    for modifier_id in line.modifier_ids or []:
        modifier = await db.get(m.RestaurantModifier, modifier_id)
        if modifier is None or modifier.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Modifier not found")
        extra += float(modifier.price or 0)
        db.add(
            m.RestaurantOrderModifier(
                tenant_id=tenant_id,
                line_id=row.id,
                modifier_id=modifier.id,
                name=modifier.name,
                price=modifier.price,
            )
        )
    row.line_total = money_json(float(row.line_total) + extra)
    await db.flush()
    return row


async def _remove_order_line(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str
) -> str:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(
                line_table.c.id,
                line_table.c.tenant_id,
                line_table.c.order_id,
                line_table.c.station,
            ).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    leftover = (
        await db.execute(
            select(func.count())
            .select_from(m.RestaurantOrderLine)
            .where(m.RestaurantOrderLine.order_id == order.id)
        )
    ).scalar_one()
    if leftover <= 1:
        raise HTTPException(status_code=422, detail="Keep at least one menu item.")
    await db.execute(
        delete(m.RestaurantOrderModifier).where(m.RestaurantOrderModifier.line_id == line.id)
    )
    station = line.station or "kitchen"
    await db.execute(delete(m.RestaurantOrderLine).where(m.RestaurantOrderLine.id == line.id))
    order.notes = drop_line_course(order.notes, line.id)
    order.notes = drop_line_note(order.notes, line.id)
    order.notes = drop_line_hold(order.notes, line.id)
    order.notes = drop_line_seat(order.notes, line.id)
    order.notes = drop_line_spice(order.notes, line.id)
    order.notes = drop_line_doneness(order.notes, line.id)
    await db.flush()
    return station


async def _set_order_line_quantity(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, quantity
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(
                line_table.c.id,
                line_table.c.tenant_id,
                line_table.c.order_id,
                line_table.c.unit_price,
            ).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    qty = money_json(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Line quantity must be greater than zero")
    extras = (
        await db.execute(
            select(func.coalesce(func.sum(m.RestaurantOrderModifier.price), 0)).where(
                m.RestaurantOrderModifier.tenant_id == tenant_id,
                m.RestaurantOrderModifier.line_id == line.id,
            )
        )
    ).scalar_one()
    await db.execute(
        update(line_table)
        .where(line_table.c.id == line.id)
        .values(quantity=qty, line_total=money_json(float(line.unit_price or 0) * qty + float(extras or 0)))
    )
    await db.flush()


async def _set_order_line_price(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, unit_price
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(
                line_table.c.id,
                line_table.c.tenant_id,
                line_table.c.order_id,
                line_table.c.quantity,
            ).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    price = money_json(unit_price)
    if price < 0:
        raise HTTPException(status_code=422, detail="Line price cannot be negative")
    extras = (
        await db.execute(
            select(func.coalesce(func.sum(m.RestaurantOrderModifier.price), 0)).where(
                m.RestaurantOrderModifier.tenant_id == tenant_id,
                m.RestaurantOrderModifier.line_id == line.id,
            )
        )
    ).scalar_one()
    await db.execute(
        update(line_table)
        .where(line_table.c.id == line.id)
        .values(
            unit_price=price,
            line_total=money_json(price * float(line.quantity or 0) + float(extras or 0)),
        )
    )
    await db.flush()


async def _set_order_line_station(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, station: str
) -> str:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(
                line_table.c.id,
                line_table.c.tenant_id,
                line_table.c.order_id,
                line_table.c.station,
            ).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    next_station = str(station or "").strip().lower()
    if next_station not in {"kitchen", "bar"}:
        raise HTTPException(status_code=422, detail="Station must be kitchen or bar")
    previous = line.station or "kitchen"
    await db.execute(
        update(line_table).where(line_table.c.id == line.id).values(station=next_station)
    )
    await db.flush()
    return previous


async def _set_order_line_course(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, course: str
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(line_table.c.id, line_table.c.tenant_id, line_table.c.order_id).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    order.notes = write_line_course(order.notes, line.id, course)
    await db.flush()


async def _set_order_line_note(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, note: str | None
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(line_table.c.id, line_table.c.tenant_id, line_table.c.order_id).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    if note:
        order.notes = write_line_note(order.notes, line.id, note)
    else:
        order.notes = drop_line_note(order.notes, line.id)
    await db.flush()


async def _set_order_line_hold(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, hold: bool
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(line_table.c.id, line_table.c.tenant_id, line_table.c.order_id).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    if hold is True:
        order.notes = write_line_hold(order.notes, line.id)
    else:
        order.notes = drop_line_hold(order.notes, line.id)
    await db.flush()


async def _set_order_line_seat(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, seat
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(line_table.c.id, line_table.c.tenant_id, line_table.c.order_id).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    if seat is None:
        order.notes = drop_line_seat(order.notes, line.id)
    else:
        order.notes = write_line_seat(order.notes, line.id, seat)
    await db.flush()


async def _set_order_line_spice(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, spice
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(line_table.c.id, line_table.c.tenant_id, line_table.c.order_id).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    if spice is None:
        order.notes = drop_line_spice(order.notes, line.id)
    else:
        order.notes = write_line_spice(order.notes, line.id, spice)
    await db.flush()


async def _set_order_line_doneness(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, doneness
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(line_table.c.id, line_table.c.tenant_id, line_table.c.order_id).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    if doneness is None:
        order.notes = drop_line_doneness(order.notes, line.id)
    else:
        order.notes = write_line_doneness(order.notes, line.id, doneness)
    await db.flush()


async def _set_order_line_modifiers(
    db: AsyncSession, tenant_id: str, order: m.RestaurantOrder, line_id: str, modifier_ids: list[str]
) -> None:
    line_table = m.RestaurantOrderLine.__table__
    line = (
        await db.execute(
            select(
                line_table.c.id,
                line_table.c.tenant_id,
                line_table.c.order_id,
                line_table.c.quantity,
                line_table.c.unit_price,
            ).where(line_table.c.id == line_id)
        )
    ).first()
    if line is None or line.tenant_id != tenant_id or line.order_id != order.id:
        raise HTTPException(status_code=404, detail="Order line not found")
    chosen: list[m.RestaurantModifier] = []
    seen: set[str] = set()
    for modifier_id in modifier_ids or []:
        if modifier_id in seen:
            continue
        seen.add(modifier_id)
        modifier = await db.get(m.RestaurantModifier, modifier_id)
        if modifier is None or modifier.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Modifier not found")
        if not modifier.is_active:
            raise HTTPException(status_code=409, detail="Retired extras cannot be added.")
        group = await db.get(m.RestaurantModifierGroup, modifier.group_id)
        if group is None or group.tenant_id != tenant_id or not group.is_active:
            raise HTTPException(status_code=409, detail="Retired extra groups cannot be added.")
        chosen.append(modifier)
    await db.execute(
        delete(m.RestaurantOrderModifier).where(
            m.RestaurantOrderModifier.tenant_id == tenant_id,
            m.RestaurantOrderModifier.line_id == line.id,
        )
    )
    extra = 0.0
    for modifier in chosen:
        extra += float(modifier.price or 0)
        db.add(
            m.RestaurantOrderModifier(
                tenant_id=tenant_id,
                line_id=line.id,
                modifier_id=modifier.id,
                name=modifier.name,
                price=modifier.price,
            )
        )
    await db.execute(
        update(line_table)
        .where(line_table.c.id == line.id)
        .values(line_total=money_json(float(line.unit_price or 0) * float(line.quantity or 0) + extra))
    )
    await db.flush()


def bill_parts(subtotal: float, total: float, percent: float) -> tuple[float, float]:
    """Split a stored bill into service and tax. Service is taken first, up to the amount added on top."""
    additions = money_json(round(money_json(total) - money_json(subtotal), 2))
    if additions < 0:
        additions = 0.0
    service = money_json(round(money_json(subtotal) * float(percent or 0) / 100, 2))
    if service < 0:
        service = 0.0
    if service > additions:
        service = additions
    tax = money_json(round(additions - service, 2))
    if tax < 0:
        tax = 0.0
    return service, tax


async def service_percent(db: AsyncSession, tenant_id: str) -> float:
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or packages_svc.canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        return 0.0
    raw = tenant.document_numbering if isinstance(tenant.document_numbering, dict) else {}
    try:
        percent = float(raw.get(SERVICE_KEY) or 0)
    except (TypeError, ValueError):
        return 0.0
    if percent < 0 or percent > 30:
        return 0.0
    return percent


async def get_service_charge(db: AsyncSession, tenant_id: str) -> dict:
    return {"percent": await service_percent(db, tenant_id)}


async def save_service_charge(db: AsyncSession, tenant_id: str, percent: float | None) -> dict:
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or tenant.id != tenant_id:
        raise HTTPException(status_code=404, detail="Company not found")
    data = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    if percent is None:
        data.pop(SERVICE_KEY, None)
    else:
        data[SERVICE_KEY] = float(percent)
    tenant.document_numbering = data
    await db.flush()
    return {"percent": await service_percent(db, tenant_id)}


async def _bill_amounts(db: AsyncSession, tenant_id: str, lines: list) -> tuple[float, float]:
    subtotal = money_json(round(sum(float(row.line_total or 0) for row in lines), 2))
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or packages_svc.canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        return subtotal, subtotal
    product_ids = {row.product_id for row in lines if getattr(row, "product_id", None)}
    products: dict[str, m.Product] = {}
    if product_ids:
        products = {
            row.id: row
            for row in (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == tenant_id,
                        m.Product.id.in_(product_ids),
                    )
                )
            ).scalars()
        }
    from app import tax as tax_svc

    added_tax = 0.0
    for row in lines:
        product = products.get(row.product_id)
        if product is None:
            continue
        spec = await tax_svc.resolve_product_tax(db, tenant_id, product)
        _net, tax, _gross = spec.compute_amounts(float(row.line_total or 0))
        if (spec.pricing_mode or "exclusive") == "exclusive" and not spec.is_reverse_charge:
            added_tax = money_json(round(added_tax + tax, 2))
    percent = await service_percent(db, tenant_id)
    service = money_json(round(subtotal * percent / 100, 2))
    if service > 0:
        default = await tax_svc.get_default_tax_rate(db, tenant_id)
        if (
            default is not None
            and default.is_active
            and (default.pricing_mode or "exclusive") == "exclusive"
            and not default.is_reverse_charge
        ):
            _net, service_tax, _gross = tax_svc.compute_tax_amounts(
                service, float(default.rate or 0), "exclusive"
            )
            added_tax = money_json(round(added_tax + service_tax, 2))
    total = money_json(round(subtotal + service + added_tax, 2))
    return subtotal, total


async def _refresh_order_totals(db: AsyncSession, order: m.RestaurantOrder) -> None:
    lines = list(
        (
            await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
        ).scalars()
    )
    subtotal, total = await _bill_amounts(db, order.tenant_id, lines)
    order.subtotal = subtotal
    order.total_amount = total
    await db.flush()


async def _free_table_if_unused(db: AsyncSession, tenant_id: str, table_id: str | None, except_order_id: str) -> None:
    if not table_id:
        return
    other = (
        await db.execute(
            select(m.RestaurantOrder.id).where(
                m.RestaurantOrder.tenant_id == tenant_id,
                m.RestaurantOrder.table_id == table_id,
                m.RestaurantOrder.id != except_order_id,
                m.RestaurantOrder.status.notin_(("completed", "cancelled", "voided", "refunded")),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if other:
        return
    table = await db.get(m.RestaurantTable, table_id)
    if table is not None and table.tenant_id == tenant_id and table.status == "occupied":
        table.status = "available"


async def update_order(
    db: AsyncSession, tenant_id: str, order_id: str, payload, *, user_id: str | None
) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status not in {"open", "sent"}:
        raise HTTPException(status_code=409, detail="Order cannot be changed.")
    changed = False
    if "store_id" in getattr(payload, "model_fields_set", set()):
        raw = getattr(payload, "store_id", None)
        store_id = str(raw).strip() if raw else None
        if store_id:
            store = await db.get(m.Store, store_id)
            if store is None or store.tenant_id != tenant_id or not store.is_active:
                raise HTTPException(status_code=404, detail="Store not found")
            await _require_store_for_scoped_user(db, tenant_id, user_id, store.id)
            order.store_id = store.id
        else:
            await _require_store_for_scoped_user(db, tenant_id, user_id, None)
            order.store_id = None
        changed = True
    if payload.customer_name is not None:
        order.customer_name = optional_honest_narrative(payload.customer_name, label="customer name")
        changed = True
    if getattr(payload, "payment_method", None) is not None:
        method = str(payload.payment_method).strip().lower()
        if method == "credit":
            raise HTTPException(status_code=422, detail=BILL_CREDIT_DETAIL)
        if method not in PAYMENT_METHODS:
            raise HTTPException(status_code=422, detail="payment_method is not supported")
        order.payment_method = method
        changed = True
    if getattr(payload, "service_mode", None) is not None:
        mode = str(payload.service_mode).strip().lower()
        if mode not in SERVICE_MODES:
            raise HTTPException(status_code=422, detail="service_mode must be dine_in, takeaway, or delivery")
        previous_table = order.table_id
        if mode == "dine_in":
            table_id = (getattr(payload, "table_id", None) or "").strip() or order.table_id
            if not table_id:
                has_table = (
                    await db.execute(
                        select(m.RestaurantTable.id).where(
                            m.RestaurantTable.tenant_id == tenant_id,
                            m.RestaurantTable.is_active.is_(True),
                        ).limit(1)
                    )
                ).scalar_one_or_none()
                if has_table:
                    raise HTTPException(status_code=422, detail="Dine in needs a table.")
                order.table_id = None
            else:
                table = await db.get(m.RestaurantTable, table_id)
                if table is None or table.tenant_id != tenant_id or not table.is_active:
                    raise HTTPException(status_code=404, detail="Table not found")
                table.status = "occupied"
                order.table_id = table.id
            if previous_table and previous_table != order.table_id:
                await _free_table_if_unused(db, tenant_id, previous_table, order.id)
        else:
            order.table_id = None
            if previous_table:
                await _free_table_if_unused(db, tenant_id, previous_table, order.id)
            address, kitchen = unpack_order_notes(order.notes)
            incoming = payload.delivery_address if "delivery_address" in getattr(payload, "model_fields_set", set()) else None
            if mode == "delivery" and not address and not incoming:
                raise HTTPException(status_code=422, detail="Delivery needs an address")
            if mode != "delivery":
                order.notes = drop_order_zone(
                    pack_order_notes(delivery_address=None, notes=kitchen, course_source=order.notes)
                    if address
                    else order.notes
                )
        order.service_mode = mode
        changed = True
    if payload.notes is not None:
        address, _kitchen = unpack_order_notes(order.notes)
        order.notes = pack_order_notes(
            delivery_address=address,
            notes=optional_honest_narrative(payload.notes, label="order notes"),
            course_source=order.notes,
        )
        changed = True
    if "covers" in getattr(payload, "model_fields_set", set()):
        if payload.covers is None:
            order.notes = drop_order_covers(order.notes)
        else:
            order.notes = write_order_covers(order.notes, int(payload.covers))
        changed = True
    if "allergy" in getattr(payload, "model_fields_set", set()):
        if payload.allergy is None:
            order.notes = drop_order_allergy(order.notes)
        else:
            order.notes = write_order_allergy(order.notes, payload.allergy)
        changed = True
    if "allergen" in getattr(payload, "model_fields_set", set()):
        if payload.allergen is None:
            order.notes = drop_order_allergen(order.notes)
        else:
            order.notes = write_order_allergen(order.notes, payload.allergen)
        changed = True
    if "occasion" in getattr(payload, "model_fields_set", set()):
        if payload.occasion is None:
            order.notes = drop_order_occasion(order.notes)
        else:
            order.notes = write_order_occasion(order.notes, payload.occasion)
        changed = True
    if "phone" in getattr(payload, "model_fields_set", set()):
        if payload.phone is None:
            order.notes = drop_order_phone(order.notes)
        else:
            order.notes = write_order_phone(order.notes, payload.phone)
        changed = True
    if "pager" in getattr(payload, "model_fields_set", set()):
        if payload.pager is None:
            order.notes = drop_order_pager(order.notes)
        else:
            order.notes = write_order_pager(order.notes, payload.pager)
        changed = True
    if "ready_by" in getattr(payload, "model_fields_set", set()):
        if payload.ready_by is None:
            order.notes = drop_order_ready_by(order.notes)
        else:
            order.notes = write_order_ready_by(order.notes, payload.ready_by)
        changed = True
    if "quoted_wait" in getattr(payload, "model_fields_set", set()):
        if payload.quoted_wait is None:
            order.notes = drop_order_quoted_wait(order.notes)
        else:
            order.notes = write_order_quoted_wait(order.notes, payload.quoted_wait)
        changed = True
    if "fire_at" in getattr(payload, "model_fields_set", set()):
        if payload.fire_at is None:
            order.notes = drop_order_fire_at(order.notes)
        else:
            order.notes = write_order_fire_at(order.notes, payload.fire_at)
        changed = True
    if "packaging" in getattr(payload, "model_fields_set", set()):
        if payload.packaging is None:
            order.notes = drop_order_packaging(order.notes)
        else:
            order.notes = write_order_packaging(order.notes, payload.packaging)
        changed = True
    if "rush" in getattr(payload, "model_fields_set", set()):
        if payload.rush is True:
            order.notes = write_order_rush(order.notes)
        else:
            order.notes = drop_order_rush(order.notes)
        changed = True
    if "bill_asked" in getattr(payload, "model_fields_set", set()):
        if payload.bill_asked is True:
            order.notes = write_order_bill(order.notes)
        else:
            order.notes = drop_order_bill(order.notes)
        changed = True
    if "guest_arrived" in getattr(payload, "model_fields_set", set()):
        if payload.guest_arrived is True:
            order.notes = write_order_arrived(order.notes)
        else:
            order.notes = drop_order_arrived(order.notes)
        changed = True
    if "cutlery" in getattr(payload, "model_fields_set", set()):
        if payload.cutlery is True:
            order.notes = write_order_cutlery(order.notes)
        else:
            order.notes = drop_order_cutlery(order.notes)
        changed = True
    if "high_chair" in getattr(payload, "model_fields_set", set()):
        if payload.high_chair is True:
            order.notes = write_order_high_chair(order.notes)
        else:
            order.notes = drop_order_high_chair(order.notes)
        changed = True
    if "diet" in getattr(payload, "model_fields_set", set()):
        if payload.diet is None:
            order.notes = drop_order_diet(order.notes)
        else:
            order.notes = write_order_diet(order.notes, payload.diet)
        changed = True
    if "guest_source" in getattr(payload, "model_fields_set", set()):
        if payload.guest_source is None:
            order.notes = drop_order_guest_source(order.notes)
        else:
            order.notes = write_order_guest_source(order.notes, payload.guest_source)
        changed = True
    if "vehicle" in getattr(payload, "model_fields_set", set()):
        if payload.vehicle is None:
            order.notes = drop_order_vehicle(order.notes)
        else:
            order.notes = write_order_vehicle(order.notes, payload.vehicle)
        changed = True
    if "bay" in getattr(payload, "model_fields_set", set()):
        if payload.bay is None:
            order.notes = drop_order_bay(order.notes)
        else:
            order.notes = write_order_bay(order.notes, payload.bay)
        changed = True
    if "handoff" in getattr(payload, "model_fields_set", set()):
        if payload.handoff is None:
            order.notes = drop_order_handoff(order.notes)
        else:
            order.notes = write_order_handoff(order.notes, payload.handoff)
        changed = True
    if "guest_email" in getattr(payload, "model_fields_set", set()):
        if payload.guest_email is None:
            order.notes = drop_order_guest_email(order.notes)
        else:
            order.notes = write_order_guest_email(order.notes, payload.guest_email)
        changed = True
    if "receipt" in getattr(payload, "model_fields_set", set()):
        if payload.receipt is None:
            order.notes = drop_order_receipt(order.notes)
        else:
            order.notes = write_order_receipt(order.notes, payload.receipt)
        changed = True
    if "delivery_address" in getattr(payload, "model_fields_set", set()) and payload.delivery_address is not None:
        if order.service_mode != "delivery":
            raise HTTPException(status_code=422, detail="This order is not a delivery.")
        _address, kitchen = unpack_order_notes(order.notes)
        order.notes = pack_order_notes(
            delivery_address=str(payload.delivery_address).strip(),
            notes=kitchen,
            course_source=order.notes,
        )
        changed = True
    zone_fields = getattr(payload, "model_fields_set", set())
    if order.service_mode == "delivery" and (
        "delivery_zone" in zone_fields or getattr(payload, "service_mode", None) is not None
    ):
        zone = await match_delivery_zone(
            db,
            tenant_id,
            payload.delivery_zone if "delivery_zone" in zone_fields else zone_for_order(order.notes),
        )
        if zone:
            order.notes = write_order_zone(order.notes, zone)
        changed = True
    elif order.service_mode != "delivery":
        stripped = drop_order_zone(order.notes)
        if stripped != order.notes:
            order.notes = stripped
            changed = True
    added_stations: set[str] = set()
    removed_stations: set[str] = set()
    for change in getattr(payload, "line_quantities", None) or []:
        await _set_order_line_quantity(db, tenant_id, order, change.line_id, change.quantity)
        changed = True
    for change in getattr(payload, "line_prices", None) or []:
        await _set_order_line_price(db, tenant_id, order, change.line_id, change.unit_price)
        changed = True
    for change in getattr(payload, "line_courses", None) or []:
        await _set_order_line_course(db, tenant_id, order, change.line_id, change.course)
        changed = True
    for change in getattr(payload, "line_notes", None) or []:
        await _set_order_line_note(db, tenant_id, order, change.line_id, change.note)
        changed = True
    for change in getattr(payload, "line_holds", None) or []:
        await _set_order_line_hold(db, tenant_id, order, change.line_id, bool(change.hold))
        changed = True
    for change in getattr(payload, "line_seats", None) or []:
        await _set_order_line_seat(db, tenant_id, order, change.line_id, change.seat)
        changed = True
    for change in getattr(payload, "line_spices", None) or []:
        await _set_order_line_spice(db, tenant_id, order, change.line_id, change.spice)
        changed = True
    for change in getattr(payload, "line_doneness", None) or []:
        await _set_order_line_doneness(db, tenant_id, order, change.line_id, change.doneness)
        changed = True
    for change in getattr(payload, "line_stations", None) or []:
        previous = await _set_order_line_station(db, tenant_id, order, change.line_id, change.station)
        next_station = str(change.station).strip().lower()
        if previous != next_station:
            removed_stations.add(previous)
            added_stations.add(next_station)
        changed = True
    for change in getattr(payload, "line_modifiers", None) or []:
        await _set_order_line_modifiers(db, tenant_id, order, change.line_id, list(change.modifier_ids or []))
        changed = True
    for line_id in payload.remove_line_ids or []:
        removed_stations.add(await _remove_order_line(db, tenant_id, order, line_id))
        changed = True
    for line in payload.lines or []:
        row = await _add_order_line(db, tenant_id, order, line)
        course = getattr(line, "course", None)
        if course:
            order.notes = write_line_course(order.notes, row.id, str(course))
        item_note = getattr(line, "note", None)
        if item_note:
            order.notes = write_line_note(order.notes, row.id, str(item_note))
        if getattr(line, "hold", None) is True:
            order.notes = write_line_hold(order.notes, row.id)
        if getattr(line, "seat", None) is not None:
            order.notes = write_line_seat(order.notes, row.id, line.seat)
        if getattr(line, "spice", None):
            order.notes = write_line_spice(order.notes, row.id, line.spice)
        if getattr(line, "doneness", None):
            order.notes = write_line_doneness(order.notes, row.id, line.doneness)
        added_stations.add(row.station or "kitchen")
        changed = True
    if not changed:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    await _refresh_order_totals(db, order)
    if order.status == "sent" and (added_stations or removed_stations):
        tickets = list(
            (
                await db.execute(
                    select(m.RestaurantKitchenTicket).where(m.RestaurantKitchenTicket.order_id == order.id)
                )
            ).scalars()
        )
        by_station = {ticket.station: ticket for ticket in tickets}
        for station in added_stations:
            ticket = by_station.get(station)
            if ticket is None:
                db.add(
                    m.RestaurantKitchenTicket(
                        tenant_id=tenant_id, order_id=order.id, station=station, status="queued"
                    )
                )
            elif ticket.status in {"ready", "done"}:
                ticket.status = "queued"
        leftover_lines = list(
            (
                await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
            ).scalars()
        )
        leftover_stations = {row.station or "kitchen" for row in leftover_lines}
        empty_queued = [
            ticket.id
            for ticket in tickets
            if ticket.station not in leftover_stations and ticket.status == "queued"
        ]
        if empty_queued:
            await db.execute(
                delete(m.RestaurantKitchenTicket).where(m.RestaurantKitchenTicket.id.in_(empty_queued))
            )
        await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_order_updated",
        entity="restaurant_order",
        entity_id=order.id,
        details={"order_number": order.order_number, "total": money_json(order.total_amount)},
    )
    return order


async def _order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None = None) -> m.RestaurantOrder:
    row = await db.get(m.RestaurantOrder, order_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    allowed = await _allowed_stores(db, tenant_id, user_id)
    if allowed is not None and row.store_id not in set(allowed):
        raise HTTPException(status_code=404, detail="Order not found")
    return row


async def send_to_kitchen(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status in {"completed", "cancelled", "voided", "refunded"}:
        raise HTTPException(status_code=409, detail="Order cannot be sent to the kitchen")
    existing = (
        await db.execute(
            select(m.RestaurantKitchenTicket).where(m.RestaurantKitchenTicket.order_id == order.id)
        )
    ).scalars().first()
    if existing is None:
        lines = (
            await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
        ).scalars()
        stations = {line.station or "kitchen" for line in lines} or {"kitchen"}
        for station in stations:
            db.add(
                m.RestaurantKitchenTicket(
                    tenant_id=tenant_id, order_id=order.id, station=station, status="queued"
                )
            )
    if order.status == "open":
        order.status = "sent"
    await db.flush()
    return order


async def expand_pos_recipe_items(
    db: AsyncSession, tenant_id: str, items: list[dict], reference_type: str
) -> list[dict]:
    """Restaurant till sales and returns use recipe ingredients. Other industries keep the sold item."""
    if reference_type not in {"pos_sale", "sales_return"}:
        return items
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or packages_svc.canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        return items
    expanded: list[dict] = []
    for item in items:
        product_id = item.get("product_id")
        qty = money_json(item.get("quantity") or 0)
        lines = await _recipe_lines(db, tenant_id, str(product_id)) if product_id else []
        if not lines:
            expanded.append(item)
            continue
        for ingredient in lines:
            need = money_json(float(ingredient.quantity) * float(qty))
            if need <= 0:
                continue
            expanded.append({"product_id": ingredient.ingredient_id, "quantity": need})
    return expanded


async def _recipe_lines(db: AsyncSession, tenant_id: str, product_id: str) -> list[m.RestaurantRecipeLine]:
    recipe = (
        await db.execute(
            select(m.RestaurantRecipe).where(
                m.RestaurantRecipe.tenant_id == tenant_id,
                m.RestaurantRecipe.product_id == product_id,
                m.RestaurantRecipe.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if recipe is None:
        return []
    return list(
        (
            await db.execute(
                select(m.RestaurantRecipeLine).where(m.RestaurantRecipeLine.recipe_id == recipe.id)
            )
        ).scalars()
    )


async def _line_stock_moves(db: AsyncSession, tenant_id: str, product_id: str, quantity) -> list[tuple[str, float]]:
    """Recipe ingredients, or the sold item when that menu item has no recipe."""
    qty = money_json(quantity)
    if qty <= 0:
        return []
    ingredients = await _recipe_lines(db, tenant_id, product_id)
    if ingredients:
        moves: list[tuple[str, float]] = []
        for ingredient in ingredients:
            need = money_json(float(ingredient.quantity) * float(qty))
            if need > 0:
                moves.append((ingredient.ingredient_id, need))
        return moves
    return [(product_id, qty)]


async def sale_line_cost(db: AsyncSession, tenant_id: str, product_id: str, quantity) -> float:
    """Cost of one restaurant sale line: recipe ingredients, or the item itself."""
    moves = await _line_stock_moves(db, tenant_id, product_id, quantity)
    return await accounting.compute_standard_cogs(
        db,
        tenant_id=tenant_id,
        lines=[{"product_id": pid, "quantity": need} for pid, need in moves],
    )


async def _bill_warehouse_id(db: AsyncSession, tenant_id: str, store_id: str | None) -> str | None:
    """Active warehouse for the bill's store. Does not create one."""
    if not store_id:
        return None
    return (
        await db.execute(
            select(m.Warehouse.id)
            .where(
                m.Warehouse.tenant_id == tenant_id,
                m.Warehouse.store_id == store_id,
                m.Warehouse.is_active.is_(True),
            )
            .order_by(m.Warehouse.code.asc(), m.Warehouse.id.asc())
        )
    ).scalars().first()


async def _warehouse_on_hand(db: AsyncSession, tenant_id: str, warehouse_id: str, product_id: str) -> float:
    qty = (
        await db.execute(
            select(m.WarehouseStock.quantity).where(
                m.WarehouseStock.tenant_id == tenant_id,
                m.WarehouseStock.warehouse_id == warehouse_id,
                m.WarehouseStock.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    return money_json(qty or 0)


async def _refund_warehouse_id(
    db: AsyncSession, tenant_id: str, order_id: str, product_id: str, need: float
) -> str | None:
    """Warehouse that this bill actually took the quantity from."""
    rows = list(
        (
            await db.execute(
                select(m.StockMovement).where(
                    m.StockMovement.tenant_id == tenant_id,
                    m.StockMovement.reference_type == "restaurant_order",
                    m.StockMovement.reference_id == order_id,
                    m.StockMovement.product_id == product_id,
                    m.StockMovement.warehouse_id.is_not(None),
                    m.StockMovement.movement_type.in_(("stock_out", "stock_in")),
                )
            )
        ).scalars().all()
    )
    outs = [
        row
        for row in rows
        if row.movement_type == "stock_out" and abs(abs(money_json(row.quantity or 0)) - need) < 0.001
    ]
    restored = sum(
        1
        for row in rows
        if row.movement_type == "stock_in" and abs(abs(money_json(row.quantity or 0)) - need) < 0.001
    )
    if restored >= len(outs):
        return None
    return outs[restored].warehouse_id


async def _stamp_bill_movement_warehouse(
    db: AsyncSession,
    *,
    tenant_id: str,
    order_id: str,
    product_id: str,
    movement_type: str,
    need: float,
    warehouse_id: str,
) -> None:
    rows = list(
        (
            await db.execute(
                select(m.StockMovement).where(
                    m.StockMovement.tenant_id == tenant_id,
                    m.StockMovement.reference_type == "restaurant_order",
                    m.StockMovement.reference_id == order_id,
                    m.StockMovement.product_id == product_id,
                    m.StockMovement.movement_type == movement_type,
                    m.StockMovement.warehouse_id.is_(None),
                )
            )
        ).scalars().all()
    )
    for row in rows:
        if abs(abs(money_json(row.quantity or 0)) - need) < 0.001:
            row.warehouse_id = warehouse_id
            await db.flush()
            return


async def _deduct_or_restore(db, tenant_id, order, *, user_id, sign: float) -> None:
    lines = (
        await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
    ).scalars()
    for line in lines:
        for product_id, need in await _line_stock_moves(db, tenant_id, line.product_id, line.quantity):
            delta = money_json(need * sign)
            if delta == 0:
                continue
            warehouse_id = None
            if sign < 0:
                candidate = await _bill_warehouse_id(db, tenant_id, order.store_id)
                if candidate and await _warehouse_on_hand(db, tenant_id, candidate, product_id) + 1e-9 >= need:
                    warehouse_id = candidate
            else:
                warehouse_id = await _refund_warehouse_id(db, tenant_id, order.id, product_id, need)
            await inventory.apply_stock_change(
                db,
                tenant_id=tenant_id,
                product_id=product_id,
                quantity_delta=delta,
                movement_type="stock_out" if sign < 0 else "stock_in",
                user_id=user_id,
                reference_type="restaurant_order",
                reference_id=order.id,
                notes=f"Restaurant order {order.order_number}",
            )
            if not warehouse_id:
                continue
            await inventory.apply_warehouse_stock_change(
                db,
                tenant_id=tenant_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                quantity_delta=delta,
            )
            await _stamp_bill_movement_warehouse(
                db,
                tenant_id=tenant_id,
                order_id=order.id,
                product_id=product_id,
                movement_type="stock_out" if sign < 0 else "stock_in",
                need=need,
                warehouse_id=warehouse_id,
            )


async def _order_stock_lines(db: AsyncSession, tenant_id: str, order: m.RestaurantOrder) -> list[dict]:
    """Quantities a bill takes off hand: recipe ingredients, or the item itself."""
    lines = (
        await db.execute(select(m.RestaurantOrderLine).where(m.RestaurantOrderLine.order_id == order.id))
    ).scalars()
    stock_lines: list[dict] = []
    for line in lines:
        for product_id, need in await _line_stock_moves(db, tenant_id, line.product_id, line.quantity):
            stock_lines.append({"product_id": product_id, "quantity": need})
    return stock_lines


async def _post_sale_journal(db, tenant_id, order, *, user_id, reverse: bool) -> str | None:
    amount = money_json(order.total_amount)
    if amount <= 0:
        return order.journal_entry_id
    await accounting.ensure_default_accounts(db, tenant_id)
    debit_code, _label = accounting.pos_debit_account_for_payment_method(order.payment_method)
    _service, tax = bill_parts(money_json(order.subtotal), amount, await service_percent(db, tenant_id))
    revenue_amount = money_json(round(amount - tax, 2))
    description = f"Restaurant refund {order.order_number}" if reverse else f"Restaurant sale {order.order_number}"
    if reverse:
        lines = [
            {"account_code": "4000", "debit": revenue_amount, "credit": 0, "description": description},
            {"account_code": debit_code, "debit": 0, "credit": amount, "description": description},
        ]
        if tax > 0:
            lines.insert(1, {"account_code": "2100", "debit": tax, "credit": 0, "description": description})
    else:
        lines = [
            {"account_code": debit_code, "debit": amount, "credit": 0, "description": description},
            {"account_code": "4000", "debit": 0, "credit": revenue_amount, "description": description},
        ]
        if tax > 0:
            lines.append({"account_code": "2100", "debit": 0, "credit": tax, "description": description})
    cogs = await accounting.compute_standard_cogs(
        db, tenant_id=tenant_id, lines=await _order_stock_lines(db, tenant_id, order)
    )
    accounting.append_cogs_lines(lines, cogs, reverse=reverse)
    entry = await accounting.post_journal_entry(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        description=description,
        lines=lines,
        reference=order.order_number,
        source_type="restaurant_order",
        source_id=order.id,
    )
    return entry.id


async def _release_table_if_clear(db: AsyncSession, tenant_id: str, table_id: str | None) -> None:
    """Free a table only when no open order and no seated party still hold it."""
    if not table_id:
        return
    open_order = (
        await db.execute(
            select(m.RestaurantOrder.id).where(
                m.RestaurantOrder.tenant_id == tenant_id,
                m.RestaurantOrder.table_id == table_id,
                m.RestaurantOrder.status.in_(tuple(OPEN_STATUSES)),
            ).limit(1)
        )
    ).scalar_one_or_none()
    if open_order is not None:
        return
    seated = (
        await db.execute(
            select(m.RestaurantBooking.id).where(
                m.RestaurantBooking.tenant_id == tenant_id,
                m.RestaurantBooking.table_id == table_id,
                m.RestaurantBooking.status == "seated",
            ).limit(1)
        )
    ).scalar_one_or_none()
    if seated is not None:
        return
    table = await db.get(m.RestaurantTable, table_id)
    if table is not None and table.tenant_id == tenant_id and table.status == "occupied":
        table.status = "available"


async def complete_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status == "completed":
        return order
    if order.status in {"cancelled", "voided", "refunded"}:
        raise HTTPException(status_code=409, detail="Order cannot be completed")
    if (order.payment_method or "").strip().lower() == "credit":
        raise HTTPException(status_code=409, detail=BILL_CREDIT_DETAIL)
    await _refresh_order_totals(db, order)
    await _deduct_or_restore(db, tenant_id, order, user_id=user_id, sign=-1)
    order.journal_entry_id = await _post_sale_journal(db, tenant_id, order, user_id=user_id, reverse=False)
    order.status = "completed"
    order.completed_at = _now()
    await till_svc.stamp_paid_order(db, order, user_id=user_id)
    await _release_table_if_clear(db, tenant_id, order.table_id)
    tickets = (
        await db.execute(
            select(m.RestaurantKitchenTicket).where(m.RestaurantKitchenTicket.order_id == order.id)
        )
    ).scalars()
    for ticket in tickets:
        ticket.status = "done"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_completed", entity="restaurant_order", entity_id=order.id,
        details={"total": money_json(order.total_amount), "payment_method": order.payment_method},
    )
    return order


async def cancel_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None, void: bool) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status in {"completed", "refunded"}:
        raise HTTPException(status_code=409, detail="Completed orders must be refunded")
    if order.status in {"cancelled", "voided"}:
        return order
    order.status = "voided" if void else "cancelled"
    await _release_table_if_clear(db, tenant_id, order.table_id)
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_voided" if void else "restaurant_order_cancelled",
        entity="restaurant_order", entity_id=order.id, details={"status": order.status},
    )
    return order


async def refund_order(db: AsyncSession, tenant_id: str, order_id: str, *, user_id: str | None) -> m.RestaurantOrder:
    order = await _order(db, tenant_id, order_id, user_id=user_id)
    if order.status == "refunded":
        return order
    if order.status != "completed":
        raise HTTPException(status_code=409, detail="Only a completed order can be refunded")
    await _deduct_or_restore(db, tenant_id, order, user_id=user_id, sign=1)
    await _post_sale_journal(db, tenant_id, order, user_id=user_id, reverse=True)
    order.status = "refunded"
    await till_svc.record_cash_refund(db, order, user_id=user_id)
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_order_refunded", entity="restaurant_order", entity_id=order.id,
        details={"total": money_json(order.total_amount)},
    )
    return order


async def _server_names(db: AsyncSession, tenant_id: str, user_ids: set[str]) -> dict[str, str]:
    ids = {row for row in user_ids if row}
    if not ids:
        return {}
    users = (
        await db.execute(
            select(m.User).where(
                m.User.tenant_id == tenant_id,
                m.User.id.in_(ids),
            )
        )
    ).scalars()
    names: dict[str, str] = {}
    for user in users:
        name = (user.full_name or "").strip()
        if name:
            names[user.id] = name
    return names


async def list_orders(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[m.RestaurantOrder]:
    stmt = (
        select(m.RestaurantOrder)
        .where(m.RestaurantOrder.tenant_id == tenant_id)
        .order_by(m.RestaurantOrder.created_at.desc())
    )
    scope = _store_clause(m.RestaurantOrder.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


def _guest_key(name: str | None, phone: str | None) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 7:
        return "p:" + digits[-9:]
    text = " ".join((name or "").split()).lower()
    if text and text not in {"walk-in", "walk in", "guest"}:
        return "n:" + text
    return None


async def list_guests(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[dict]:
    """Restaurant guests, gathered from their orders and bookings (no retail customer records)."""
    orders = [row for row in await list_orders(db, tenant_id, user_id=user_id) if row.status not in {"cancelled", "voided"}]
    guests: dict[str, dict] = {}

    def guest(key: str, name: str | None, phone: str | None) -> dict:
        row = guests.get(key)
        if row is None:
            row = guests[key] = {
                "key": key, "name": None, "phone": None, "email": None, "allergy": None,
                "visits": 0, "bookings": 0, "spent": 0.0, "last_visit": None, "dishes": {},
            }
        if name and not row["name"]:
            row["name"] = " ".join(name.split())
        if phone and not row["phone"]:
            row["phone"] = phone
        return row

    paid_order_guest: dict[str, str] = {}
    for order in orders:
        phone = phone_for_order(order.notes)
        key = _guest_key(order.customer_name, phone)
        if key is None:
            continue
        row = guest(key, order.customer_name, phone)
        row["visits"] += 1
        row["email"] = row["email"] or guest_email_for_order(order.notes)
        row["allergy"] = row["allergy"] or allergy_for_order(order.notes)
        if order.status == "completed":
            row["spent"] += float(order.total_amount or 0)
            paid_order_guest[order.id] = key
        seen = order.completed_at or order.created_at
        if seen and (row["last_visit"] is None or seen > row["last_visit"]):
            row["last_visit"] = seen
    for booking in await list_bookings(db, tenant_id):
        if booking.status == "cancelled":
            continue
        key = _guest_key(booking.guest_name, booking.phone)
        if key is None:
            continue
        row = guest(key, booking.guest_name, booking.phone)
        row["bookings"] += 1
    if paid_order_guest:
        lines = (
            await db.execute(
                select(m.RestaurantOrderLine.order_id, m.RestaurantOrderLine.quantity, m.Product.name)
                .join(m.Product, m.Product.id == m.RestaurantOrderLine.product_id)
                .where(
                    m.RestaurantOrderLine.tenant_id == tenant_id,
                    m.RestaurantOrderLine.order_id.in_(set(paid_order_guest)),
                )
            )
        ).all()
        for order_id, qty, dish in lines:
            dishes = guests[paid_order_guest[order_id]]["dishes"]
            dishes[dish] = dishes.get(dish, 0) + float(qty or 0)
    out = []
    for row in guests.values():
        dishes = row.pop("dishes")
        favourite = max(dishes.items(), key=lambda kv: kv[1])[0] if dishes else None
        last = row["last_visit"]
        out.append({
            **row,
            "spent": money_json(round(row["spent"], 2)),
            "favourite_dish": favourite,
            "last_visit": last.isoformat() if last else None,
        })
    out.sort(key=lambda r: (r["last_visit"] or ""), reverse=True)
    return out


async def list_kitchen(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> list[m.RestaurantKitchenTicket]:
    stmt = (
        select(m.RestaurantKitchenTicket)
        .join(m.RestaurantOrder, m.RestaurantOrder.id == m.RestaurantKitchenTicket.order_id)
        .where(
            m.RestaurantKitchenTicket.tenant_id == tenant_id,
            m.RestaurantKitchenTicket.status.in_(("queued", "preparing", "ready")),
        )
        .order_by(m.RestaurantKitchenTicket.created_at)
    )
    scope = _store_clause(m.RestaurantOrder.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        stmt = stmt.where(scope)
    return list((await db.execute(stmt)).scalars())


def serialize_order(row: m.RestaurantOrder) -> dict:
    address, kitchen = unpack_order_notes(row.notes)
    return {
        "id": row.id,
        "order_number": row.order_number,
        "service_mode": row.service_mode,
        "table_id": row.table_id,
        "customer_name": row.customer_name,
        "status": row.status,
        "payment_method": row.payment_method,
        "subtotal": money_json(row.subtotal),
        "total_amount": money_json(row.total_amount),
        "store_id": row.store_id,
        "notes": kitchen,
        "delivery_address": address,
        "delivery_zone": zone_for_order(row.notes),
        "channel": channel_for_order(row.notes),
        "covers": covers_for_order(row.notes),
        "allergy": allergy_for_order(row.notes),
        "allergen": allergen_for_order(row.notes),
        "occasion": occasion_for_order(row.notes),
        "phone": phone_for_order(row.notes),
        "pager": pager_for_order(row.notes),
        "ready_by": ready_by_for_order(row.notes),
        "quoted_wait": quoted_wait_for_order(row.notes),
        "fire_at": fire_at_for_order(row.notes),
        "packaging": packaging_for_order(row.notes),
        "rush": rush_for_order(row.notes),
        "bill_asked": bill_asked_for_order(row.notes),
        "guest_arrived": guest_arrived_for_order(row.notes),
        "cutlery": cutlery_for_order(row.notes),
        "high_chair": high_chair_for_order(row.notes),
        "diet": diet_for_order(row.notes),
        "guest_source": guest_source_for_order(row.notes),
        "vehicle": vehicle_for_order(row.notes),
        "bay": bay_for_order(row.notes),
        "handoff": handoff_for_order(row.notes),
        "guest_email": guest_email_for_order(row.notes),
        "receipt": receipt_for_order(row.notes),
        "opened_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "till_shift_id": row.till_shift_id,
    }


async def present_orders(
    db: AsyncSession,
    tenant_id: str,
    orders: list[m.RestaurantOrder],
) -> list[dict]:
    if not orders:
        return []
    percent = await service_percent(db, tenant_id)
    order_ids = {row.id for row in orders}
    lines = list(
        (
            await db.execute(
                select(m.RestaurantOrderLine).where(
                    m.RestaurantOrderLine.tenant_id == tenant_id,
                    m.RestaurantOrderLine.order_id.in_(order_ids),
                )
            )
        ).scalars()
    )
    product_ids = {line.product_id for line in lines}
    products = {}
    if product_ids:
        products = {
            row.id: row
            for row in (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == tenant_id,
                        m.Product.id.in_(product_ids),
                    )
                )
            ).scalars()
        }
    line_ids = {line.id for line in lines}
    modifiers = []
    if line_ids:
        modifiers = list(
            (
                await db.execute(
                    select(m.RestaurantOrderModifier).where(
                        m.RestaurantOrderModifier.tenant_id == tenant_id,
                        m.RestaurantOrderModifier.line_id.in_(line_ids),
                    )
                )
            ).scalars()
        )
    has_prep = await _line_prep_status_live(db)
    tickets = []
    if not has_prep and orders:
        tickets = list(
            (
                await db.execute(
                    select(m.RestaurantKitchenTicket).where(
                        m.RestaurantKitchenTicket.tenant_id == tenant_id,
                        m.RestaurantKitchenTicket.order_id.in_({order.id for order in orders}),
                    )
                )
            ).scalars()
        )
    ticket_by = {(row.order_id, row.station or "kitchen"): row for row in tickets}
    servers = await _server_names(db, tenant_id, {order.created_by for order in orders if order.created_by})
    out = []
    for order in orders:
        items = []
        for line in lines:
            if line.order_id != order.id:
                continue
            product = products.get(line.product_id)
            station = line.station or "kitchen"
            items.append(
                {
                    "id": line.id,
                    "quantity": money_json(line.quantity),
                    "unit_price": money_json(line.unit_price),
                    "line_total": money_json(line.line_total),
                    "name": product.name if product else "Item",
                    "station": station,
                    "modifiers": [mod.name for mod in modifiers if mod.line_id == line.id],
                    "modifier_ids": [mod.modifier_id for mod in modifiers if mod.line_id == line.id],
                    "course": course_for_line(order.notes, line.id),
                    "note": note_for_line(order.notes, line.id),
                    "hold": hold_for_line(order.notes, line.id),
                    "seat": seat_for_line(order.notes, line.id),
                    "spice": spice_for_line(order.notes, line.id),
                    "doneness": doneness_for_line(order.notes, line.id),
                    "prep_status": _item_prep_status(line, ticket_by.get((order.id, station)), has_prep=has_prep),
                }
            )
        service, tax = bill_parts(money_json(order.subtotal), money_json(order.total_amount), percent)
        out.append({
            **serialize_order(order),
            "server": servers.get(order.created_by or ""),
            "items": items,
            "tax_amount": tax,
            "service_amount": service,
        })
    return out


def serialize_ticket(row: m.RestaurantKitchenTicket) -> dict:
    return {
        "id": row.id,
        "order_id": row.order_id,
        "station": row.station,
        "status": row.status,
    }


async def present_kitchen(
    db: AsyncSession,
    tenant_id: str,
    tickets: list[m.RestaurantKitchenTicket],
) -> list[dict]:
    if not tickets:
        return []
    order_ids = {ticket.order_id for ticket in tickets}
    orders = {
        row.id: row
        for row in (
            await db.execute(
                select(m.RestaurantOrder).where(
                    m.RestaurantOrder.tenant_id == tenant_id,
                    m.RestaurantOrder.id.in_(order_ids),
                )
            )
        ).scalars()
    }
    table_ids = {row.table_id for row in orders.values() if row.table_id}
    tables = {}
    if table_ids:
        tables = {
            row.id: row
            for row in (
                await db.execute(
                    select(m.RestaurantTable).where(
                        m.RestaurantTable.tenant_id == tenant_id,
                        m.RestaurantTable.id.in_(table_ids),
                    )
                )
            ).scalars()
        }
    lines = list(
        (
            await db.execute(
                select(m.RestaurantOrderLine).where(
                    m.RestaurantOrderLine.tenant_id == tenant_id,
                    m.RestaurantOrderLine.order_id.in_(order_ids),
                )
            )
        ).scalars()
    )
    product_ids = {line.product_id for line in lines}
    products = {}
    if product_ids:
        products = {
            row.id: row
            for row in (
                await db.execute(
                    select(m.Product).where(
                        m.Product.tenant_id == tenant_id,
                        m.Product.id.in_(product_ids),
                    )
                )
            ).scalars()
        }
    line_ids = {line.id for line in lines}
    modifiers = []
    if line_ids:
        modifiers = list(
            (
                await db.execute(
                    select(m.RestaurantOrderModifier).where(
                        m.RestaurantOrderModifier.tenant_id == tenant_id,
                        m.RestaurantOrderModifier.line_id.in_(line_ids),
                    )
                )
            ).scalars()
        )
    has_prep = await _line_prep_status_live(db)
    servers = await _server_names(
        db,
        tenant_id,
        {order.created_by for order in orders.values() if order.created_by},
    )
    out = []
    for ticket in tickets:
        order = orders.get(ticket.order_id)
        station = ticket.station or "kitchen"
        items = []
        for line in lines:
            if line.order_id != ticket.order_id or (line.station or "kitchen") != station:
                continue
            product = products.get(line.product_id)
            items.append(
                {
                    "id": line.id,
                    "quantity": money_json(line.quantity),
                    "name": product.name if product else "Item",
                    "modifiers": [mod.name for mod in modifiers if mod.line_id == line.id],
                    "course": course_for_line(order.notes if order else None, line.id),
                    "note": note_for_line(order.notes if order else None, line.id),
                    "hold": hold_for_line(order.notes if order else None, line.id),
                    "seat": seat_for_line(order.notes if order else None, line.id),
                    "spice": spice_for_line(order.notes if order else None, line.id),
                    "doneness": doneness_for_line(order.notes if order else None, line.id),
                    "prep_status": _item_prep_status(line, ticket, has_prep=has_prep),
                }
            )
        table = tables.get(order.table_id) if order and order.table_id else None
        address, kitchen = unpack_order_notes(order.notes if order else None)
        out.append(
            {
                **serialize_ticket(ticket),
                "order_number": order.order_number if order else None,
                "service_mode": order.service_mode if order else None,
                "table_code": table.code if table else None,
                "customer_name": order.customer_name if order else None,
                "notes": kitchen,
                "delivery_address": address,
                "delivery_zone": zone_for_order(order.notes if order else None),
                "channel": channel_for_order(order.notes if order else None),
                "covers": covers_for_order(order.notes if order else None),
                "allergy": allergy_for_order(order.notes if order else None),
                "allergen": allergen_for_order(order.notes if order else None),
                "occasion": occasion_for_order(order.notes if order else None),
                "phone": phone_for_order(order.notes if order else None),
                "pager": pager_for_order(order.notes if order else None),
                "ready_by": ready_by_for_order(order.notes if order else None),
                "quoted_wait": quoted_wait_for_order(order.notes if order else None),
                "fire_at": fire_at_for_order(order.notes if order else None),
                "packaging": packaging_for_order(order.notes if order else None),
                "rush": rush_for_order(order.notes if order else None),
                "bill_asked": bill_asked_for_order(order.notes if order else None),
                "guest_arrived": guest_arrived_for_order(order.notes if order else None),
                "cutlery": cutlery_for_order(order.notes if order else None),
                "high_chair": high_chair_for_order(order.notes if order else None),
                "diet": diet_for_order(order.notes if order else None),
                "guest_source": guest_source_for_order(order.notes if order else None),
                "vehicle": vehicle_for_order(order.notes if order else None),
                "bay": bay_for_order(order.notes if order else None),
                "handoff": handoff_for_order(order.notes if order else None),
                "guest_email": guest_email_for_order(order.notes if order else None),
                "receipt": receipt_for_order(order.notes if order else None),
                "server": servers.get(order.created_by) if order and order.created_by else None,
                "opened_at": order.created_at.isoformat() if order and order.created_at else None,
                "items": items,
            }
        )
    return out


async def mark_line_ready(
    db: AsyncSession, tenant_id: str, line_id: str, *, user_id: str | None
) -> m.RestaurantOrderLine:
    line = (
        await db.execute(
            select(m.RestaurantOrderLine).where(
                m.RestaurantOrderLine.tenant_id == tenant_id,
                m.RestaurantOrderLine.id == line_id,
            )
        )
    ).scalar_one_or_none()
    if line is None:
        raise HTTPException(status_code=404, detail="Kitchen item not found")
    order = await _order(db, tenant_id, line.order_id, user_id=user_id)
    if order.status == "open":
        raise HTTPException(status_code=409, detail="Send the order to the kitchen first")
    if order.status not in {"sent", "preparing", "ready"}:
        raise HTTPException(status_code=409, detail="Order cannot be updated")
    if hold_for_line(order.notes, line.id):
        raise HTTPException(status_code=409, detail="Clear the hold before this item can be marked ready.")
    has_prep = await _line_prep_status_live(db)
    if has_prep and line.prep_status != "ready":
        line.prep_status = "ready"
    station = line.station or "kitchen"
    siblings = list(
        (
            await db.execute(
                select(m.RestaurantOrderLine).where(
                    m.RestaurantOrderLine.tenant_id == tenant_id,
                    m.RestaurantOrderLine.order_id == order.id,
                )
            )
        ).scalars()
    )
    station_lines = [row for row in siblings if (row.station or "kitchen") == station]
    tickets = list(
        (
            await db.execute(
                select(m.RestaurantKitchenTicket).where(
                    m.RestaurantKitchenTicket.tenant_id == tenant_id,
                    m.RestaurantKitchenTicket.order_id == order.id,
                )
            )
        ).scalars()
    )
    ticket = next((row for row in tickets if (row.station or "kitchen") == station), None)
    if has_prep:
        station_ready = bool(station_lines) and all((row.prep_status or "queued") == "ready" for row in station_lines)
        order_ready = bool(siblings) and all((row.prep_status or "queued") == "ready" for row in siblings)
    else:
        station_ready = True
        order_ready = all((row.station or "kitchen") == station or row.status in {"ready", "done"} for row in tickets)
    if ticket is not None and ticket.status != "done":
        ticket.status = "ready" if station_ready else "preparing"
    if order_ready:
        order.status = "ready"
    elif order.status == "sent":
        order.status = "preparing"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_line_ready", entity="restaurant_order_line", entity_id=line.id,
        details={"order_id": order.id, "prep_status": _item_prep_status(line, ticket, has_prep=has_prep)},
    )
    return line


async def start_line(
    db: AsyncSession, tenant_id: str, line_id: str, *, user_id: str | None
) -> m.RestaurantOrderLine:
    line = (
        await db.execute(
            select(m.RestaurantOrderLine).where(
                m.RestaurantOrderLine.tenant_id == tenant_id,
                m.RestaurantOrderLine.id == line_id,
            )
        )
    ).scalar_one_or_none()
    if line is None:
        raise HTTPException(status_code=404, detail="Kitchen item not found")
    order = await _order(db, tenant_id, line.order_id, user_id=user_id)
    if order.status == "open":
        raise HTTPException(status_code=409, detail="Send the order to the kitchen first")
    if order.status not in {"sent", "preparing", "ready"}:
        raise HTTPException(status_code=409, detail="Order cannot be updated")
    if hold_for_line(order.notes, line.id):
        raise HTTPException(status_code=409, detail="Clear the hold before this item can start.")
    has_prep = await _line_prep_status_live(db)
    current = (line.prep_status or "queued") if has_prep else "queued"
    if has_prep and current == "ready":
        raise HTTPException(status_code=409, detail="This item is already ready.")
    if has_prep and current != "preparing":
        line.prep_status = "preparing"
    station = line.station or "kitchen"
    ticket = (
        await db.execute(
            select(m.RestaurantKitchenTicket).where(
                m.RestaurantKitchenTicket.tenant_id == tenant_id,
                m.RestaurantKitchenTicket.order_id == order.id,
                m.RestaurantKitchenTicket.station == station,
            )
        )
    ).scalars().first()
    if ticket is not None and ticket.status not in {"ready", "done"}:
        ticket.status = "preparing"
    if order.status == "sent":
        order.status = "preparing"
    await db.flush()
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="restaurant",
        action="restaurant_line_started", entity="restaurant_order_line", entity_id=line.id,
        details={"order_id": order.id, "prep_status": _item_prep_status(line, ticket, has_prep=has_prep)},
    )
    return line


async def record_waste(
    db: AsyncSession,
    tenant_id: str,
    *,
    user_id: str | None,
    product_id: str,
    quantity,
    reason: str,
    notes: str | None = None,
    warehouse_id: str | None = None,
) -> dict:
    kind = (reason or "").strip().lower()
    if kind not in WASTE_REASONS:
        raise HTTPException(status_code=422, detail="Waste reason must be spoilage, damage, or waste.")
    qty = money_json(quantity)
    if qty <= 0:
        raise HTTPException(status_code=422, detail="Waste quantity must be greater than zero")
    tenant = await db.get(m.Tenant, tenant_id)
    if tenant is None or packages_svc.canonicalize_industry(getattr(tenant, "industry", None)) != "restaurant":
        raise HTTPException(status_code=403, detail="Restaurant is not available for this company.")
    await _require_store_for_scoped_user(db, tenant_id, user_id, None)
    product = await _product(db, tenant_id, product_id)
    await _require_waste_ingredient(db, tenant_id, product)
    warehouse = None
    if warehouse_id:
        warehouse = await db.get(m.Warehouse, warehouse_id)
        if warehouse is None or warehouse.tenant_id != tenant_id or not warehouse.is_active:
            raise HTTPException(status_code=404, detail="Warehouse not found")
    result = await catalog_svc.stock_out_with_batch(
        db,
        tenant_id=tenant_id,
        user_id=user_id or "",
        product_id=product.id,
        quantity=qty,
        notes=pack_waste_notes(
            reason=kind,
            notes=optional_honest_narrative(notes, label="waste notes"),
        ),
        warehouse_id=warehouse.id if warehouse else None,
        reference_type="damage" if kind == "damage" else "other",
    )
    move = (
        await db.execute(
            select(m.StockMovement)
            .where(
                m.StockMovement.tenant_id == tenant_id,
                m.StockMovement.product_id == product.id,
                m.StockMovement.movement_type == "stock_out",
                m.StockMovement.reference_id.is_(None),
                m.StockMovement.notes.contains(WASTE_PREFIX),
            )
            .order_by(m.StockMovement.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    cost_each = money_json(product.cost_price or 0)
    cost_amount = money_json(round(qty * cost_each, 2))
    journal_id = None
    if cost_amount > 0 and move is not None:
        await accounting.ensure_default_accounts(db, tenant_id)
        label = (product.name or "").strip()
        description = f"Restaurant waste {label}".strip() if label else "Restaurant waste"
        entry = await accounting.post_journal_entry(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            description=description,
            lines=[
                {"account_code": "6000", "debit": cost_amount, "credit": 0, "description": description},
                {"account_code": "1200", "debit": 0, "credit": cost_amount, "description": description},
            ],
            source_type="restaurant_waste",
            source_id=move.id,
        )
        journal_id = entry.id
        move.reference_id = entry.id
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_waste_recorded",
        entity="product",
        entity_id=product.id,
        details={"reason": kind, "quantity": qty},
    )
    return {
        "product_id": product.id,
        "name": product.name,
        "quantity": qty,
        "reason": kind,
        "warehouse_id": warehouse.id if warehouse else None,
        "stock_qty": money_json(result.get("stock_qty", product.stock_qty)),
        "cost_amount": cost_amount,
        "journal_entry_id": journal_id,
    }


async def list_waste(
    db: AsyncSession, tenant_id: str, user_id: str | None = None
) -> list[dict]:
    stmt = (
        select(m.StockMovement, m.Product.name)
        .join(m.Product, m.Product.id == m.StockMovement.product_id)
        .where(
            m.StockMovement.tenant_id == tenant_id,
            m.StockMovement.notes.is_not(None),
            m.StockMovement.notes.contains(WASTE_PREFIX),
        )
    )
    # Staff tied to stores see waste from their stores' warehouses (and waste with no warehouse).
    allowed = await _allowed_stores(db, tenant_id, user_id)
    if allowed is not None:
        store_warehouses = select(m.Warehouse.id).where(
            m.Warehouse.tenant_id == tenant_id, m.Warehouse.store_id.in_(list(allowed) or [""])
        )
        stmt = stmt.where(
            or_(m.StockMovement.warehouse_id.is_(None), m.StockMovement.warehouse_id.in_(store_warehouses))
        )
    rows = (await db.execute(stmt.order_by(m.StockMovement.created_at.desc()).limit(50))).all()
    out: list[dict] = []
    for move, name in rows:
        reason, leftover = unpack_waste_notes(move.notes)
        if not reason:
            continue
        out.append(
            {
                "id": move.id,
                "product_id": move.product_id,
                "name": name,
                "quantity": money_json(abs(move.quantity)),
                "reason": reason,
                "notes": leftover,
                "warehouse_id": move.warehouse_id,
                "journal_entry_id": move.reference_id,
                "created_at": move.created_at.isoformat() if move.created_at else None,
            }
        )
    return out


async def reports(db: AsyncSession, tenant_id: str, user_id: str | None = None) -> dict:
    body = await summary(db, tenant_id, user_id=user_id)
    # Same stored-unit leftover as summary: RestaurantOrder has no FX columns.
    mode_stmt = (
        select(m.RestaurantOrder.service_mode, func.count(), func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0))
        .where(m.RestaurantOrder.tenant_id == tenant_id, m.RestaurantOrder.status == "completed")
        .group_by(m.RestaurantOrder.service_mode)
    )
    scope = _store_clause(m.RestaurantOrder.store_id, await _allowed_stores(db, tenant_id, user_id))
    if scope is not None:
        mode_stmt = mode_stmt.where(scope)
    by_mode = (await db.execute(mode_stmt)).all()
    body["by_service_mode"] = [
        {"service_mode": mode, "orders": int(count), "sales": money_json(total)}
        for mode, count, total in by_mode
    ]
    tender_stmt = (
        select(m.RestaurantOrder.payment_method, func.count(), func.coalesce(func.sum(m.RestaurantOrder.total_amount), 0))
        .where(m.RestaurantOrder.tenant_id == tenant_id, m.RestaurantOrder.status == "completed")
        .group_by(m.RestaurantOrder.payment_method)
    )
    if scope is not None:
        tender_stmt = tender_stmt.where(scope)
    by_tender = (await db.execute(tender_stmt)).all()
    body["by_payment_method"] = [
        {"payment_method": method, "orders": int(count), "sales": money_json(total)}
        for method, count, total in by_tender
    ]
    if int(body.get("till_receipts") or 0) > 0:
        body["by_service_mode"].append(
            {
                "service_mode": "restaurant_till",
                "orders": int(body["till_receipts"]),
                "sales": body["till_sales_today"],
            }
        )
    return body


BOOKING_LINK_KINDS = {"existing", "new"}
BOOKING_STATUSES = {"requested", "seated", "cancelled", "finished"}


def _parse_booked_for(value: str) -> datetime:
    text = (value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Booking time must be a date and time") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    current_minute = _now().replace(second=0, microsecond=0)
    if parsed < current_minute:
        raise HTTPException(status_code=422, detail="Booking time must be now or later")
    return parsed


async def _restaurant_tenant(db: AsyncSession, *, tenant_id: str | None = None, slug: str | None = None) -> m.Tenant:
    stmt = select(m.Tenant)
    if tenant_id:
        stmt = stmt.where(m.Tenant.id == tenant_id)
    else:
        stmt = stmt.where(m.Tenant.slug == (slug or "").strip().lower())
    tenant = (await db.execute(stmt)).scalar_one_or_none()
    industry = packages_svc.canonicalize_industry(getattr(tenant, "industry", None) if tenant else None)
    if tenant is None or industry != "restaurant":
        raise HTTPException(status_code=404, detail="Restaurant booking is not available")
    return tenant


async def get_booking_link(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    row = (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    return _serialize_booking_link(tenant, row)


def _serialize_booking_link(tenant: m.Tenant, row: m.RestaurantBookingLink | None) -> dict:
    return {
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "path": f"/book/{tenant.slug}",
        "hostname": row.hostname if row else None,
        "link_kind": row.link_kind if row else None,
        "open": row is not None,
    }


async def save_booking_link(db: AsyncSession, tenant_id: str, *, hostname: str, link_kind: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    kind = (link_kind or "").strip().lower()
    if kind not in BOOKING_LINK_KINDS:
        raise HTTPException(status_code=422, detail="Booking link must be an existing website or a new domain")
    host = hostname.strip().lower().rstrip(".")
    taken = (
        await db.execute(
            select(m.RestaurantBookingLink).where(
                m.RestaurantBookingLink.hostname == host,
                m.RestaurantBookingLink.tenant_id != tenant.id,
            )
        )
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(status_code=409, detail="That website is already linked to another restaurant")
    row = (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        row = m.RestaurantBookingLink(tenant_id=tenant.id, hostname=host, link_kind=kind)
        db.add(row)
    else:
        row.hostname = host
        row.link_kind = kind
        row.updated_at = _now()
    await db.flush()
    return _serialize_booking_link(tenant, row)


async def booking_page(db: AsyncSession, slug: str) -> dict:
    tenant = await _restaurant_tenant(db, slug=slug)
    row = (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant booking is not open")
    body = _serialize_booking_link(tenant, row)
    return body


async def booking_page_for_host(db: AsyncSession, hostname: str) -> dict:
    host = (hostname or "").strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    row = (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.hostname == host))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant booking is not open")
    return await booking_page_by_tenant(db, row.tenant_id)


async def booking_page_by_tenant(db: AsyncSession, tenant_id: str) -> dict:
    tenant = await _restaurant_tenant(db, tenant_id=tenant_id)
    row = (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Restaurant booking is not open")
    return _serialize_booking_link(tenant, row)


TURN_RE = re.compile(r"\[\[turn:(60|90|120)\]\]")
TURNS = {60, 90, 120}


def clean_turn(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Turn must be 1 hour, 90 minutes, or 2 hours.") from None
    if isinstance(value, bool) or number not in TURNS:
        raise HTTPException(status_code=422, detail="Turn must be 1 hour, 90 minutes, or 2 hours.")
    return number


def turn_for_booking(raw: str | None) -> int | None:
    match = TURN_RE.search(raw or "")
    if match is None:
        return None
    return int(match.group(1))


def booking_note_text(raw: str | None) -> str | None:
    text = TURN_RE.sub("", raw or "").strip()
    return text or None


def write_booking_turn(raw: str | None, turn) -> str | None:
    number = clean_turn(turn)
    without = TURN_RE.sub("", raw or "").strip()
    token = f"[[turn:{number}]]"
    return f"{without}\n{token}".strip() if without else token


def drop_booking_turn(raw: str | None) -> str | None:
    text = TURN_RE.sub("", raw or "").strip()
    return text or None


def serialize_booking(row: m.RestaurantBooking) -> dict:
    return {
        "id": row.id,
        "booking_number": row.booking_number,
        "guest_name": row.guest_name,
        "phone": row.phone,
        "party_size": int(row.party_size or 0),
        "booked_for": row.booked_for.isoformat() if row.booked_for else None,
        "notes": booking_note_text(row.notes),
        "turn": turn_for_booking(row.notes),
        "status": row.status,
        "table_id": row.table_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def list_bookings(db: AsyncSession, tenant_id: str) -> list[m.RestaurantBooking]:
    await _restaurant_tenant(db, tenant_id=tenant_id)
    return list(
        (
            await db.execute(
                select(m.RestaurantBooking)
                .where(m.RestaurantBooking.tenant_id == tenant_id)
                .order_by(m.RestaurantBooking.booked_for.asc())
            )
        ).scalars().all()
    )


async def _new_booking(
    db: AsyncSession,
    tenant_id: str,
    *,
    guest_name: str,
    phone: str,
    party_size: int,
    booked_for: str,
    notes: str | None,
    turn: int | None = None,
) -> m.RestaurantBooking:
    name = require_honest_narrative(guest_name, label="guest name", min_length=1, max_length=180)
    when = _parse_booked_for(booked_for)
    size = int(party_size)
    if size < 1 or size > 40:
        raise HTTPException(status_code=422, detail="Party size must be from 1 to 40")
    count = (
        await db.execute(
            select(func.count()).select_from(m.RestaurantBooking).where(m.RestaurantBooking.tenant_id == tenant_id)
        )
    ).scalar_one()
    row = m.RestaurantBooking(
        tenant_id=tenant_id,
        booking_number=f"B-{int(count or 0) + 1:04d}",
        guest_name=name,
        phone=phone,
        party_size=size,
        booked_for=when,
        notes=optional_honest_narrative(TURN_RE.sub("", notes or ""), label="booking note", max_length=500),
        status="requested",
    )
    if turn:
        row.notes = write_booking_turn(row.notes, turn)
    db.add(row)
    await db.flush()
    return row


async def update_booking(
    db: AsyncSession, tenant_id: str, booking_id: str, payload, *, user_id: str | None
) -> m.RestaurantBooking:
    await _restaurant_tenant(db, tenant_id=tenant_id)
    row = (
        await db.execute(
            select(m.RestaurantBooking).where(
                m.RestaurantBooking.tenant_id == tenant_id,
                m.RestaurantBooking.id == booking_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if row.status != "requested":
        raise HTTPException(status_code=409, detail="Booking cannot be changed.")
    changed = False
    if payload.guest_name is not None:
        row.guest_name = require_honest_narrative(payload.guest_name, label="guest name", min_length=1, max_length=180)
        changed = True
    if payload.phone is not None:
        row.phone = payload.phone
        changed = True
    if payload.party_size is not None:
        size = int(payload.party_size)
        if size < 1 or size > 40:
            raise HTTPException(status_code=422, detail="Party size must be from 1 to 40")
        row.party_size = size
        changed = True
    if payload.booked_for is not None:
        row.booked_for = _parse_booked_for(payload.booked_for)
        changed = True
    if payload.notes is not None:
        kept = turn_for_booking(row.notes)
        plain = optional_honest_narrative(TURN_RE.sub("", payload.notes), label="booking note", max_length=500)
        row.notes = write_booking_turn(plain, kept) if kept is not None else plain
        changed = True
    if "turn" in getattr(payload, "model_fields_set", set()):
        if payload.turn is None:
            row.notes = drop_booking_turn(row.notes)
        else:
            row.notes = write_booking_turn(row.notes, payload.turn)
        changed = True
    if not changed:
        raise HTTPException(status_code=422, detail="Nothing to change.")
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_booking_updated",
        entity="restaurant_booking",
        entity_id=row.id,
        details={"booking_number": row.booking_number, "guest_name": row.guest_name},
    )
    return row


async def create_staff_booking(
    db: AsyncSession,
    tenant_id: str,
    *,
    guest_name: str,
    phone: str,
    party_size: int,
    booked_for: str,
    notes: str | None,
    turn: int | None = None,
) -> m.RestaurantBooking:
    await _restaurant_tenant(db, tenant_id=tenant_id)
    return await _new_booking(
        db,
        tenant_id,
        guest_name=guest_name,
        phone=phone,
        party_size=party_size,
        booked_for=booked_for,
        notes=notes,
        turn=turn,
    )


async def create_public_booking(
    db: AsyncSession,
    slug: str,
    *,
    guest_name: str,
    phone: str,
    party_size: int,
    booked_for: str,
    notes: str | None,
) -> m.RestaurantBooking:
    tenant = await _restaurant_tenant(db, slug=slug)
    link = (
        await db.execute(select(m.RestaurantBookingLink).where(m.RestaurantBookingLink.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Restaurant booking is not open")
    return await _new_booking(
        db,
        tenant.id,
        guest_name=guest_name,
        phone=phone,
        party_size=party_size,
        booked_for=booked_for,
        notes=notes,
    )


async def set_booking_status(
    db: AsyncSession,
    tenant_id: str,
    booking_id: str,
    status: str,
    *,
    table_id: str | None = None,
) -> m.RestaurantBooking:
    await _restaurant_tenant(db, tenant_id=tenant_id)
    if status not in {"seated", "cancelled"}:
        raise HTTPException(status_code=422, detail="Booking can be seated or cancelled")
    row = (
        await db.execute(
            select(m.RestaurantBooking).where(
                m.RestaurantBooking.tenant_id == tenant_id,
                m.RestaurantBooking.id == booking_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if row.status != "requested":
        raise HTTPException(status_code=409, detail="This booking is already closed")
    if status == "seated" and table_id:
        table = await db.get(m.RestaurantTable, table_id)
        if table is None or table.tenant_id != tenant_id or not table.is_active:
            raise HTTPException(status_code=404, detail="Table not found")
        if table.status not in {"available", "held"}:
            raise HTTPException(status_code=409, detail="Table is not available")
        if int(table.seats or 0) < int(row.party_size or 0):
            raise HTTPException(status_code=422, detail="Table is smaller than the party")
        table.status = "occupied"
        row.table_id = table.id
    row.status = status
    await db.flush()
    return row


async def finish_booking(db: AsyncSession, tenant_id: str, booking_id: str) -> m.RestaurantBooking:
    """End a seated visit. Free the table unless an open order still uses it."""
    await _restaurant_tenant(db, tenant_id=tenant_id)
    row = (
        await db.execute(
            select(m.RestaurantBooking).where(
                m.RestaurantBooking.tenant_id == tenant_id,
                m.RestaurantBooking.id == booking_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if row.status != "seated":
        raise HTTPException(status_code=409, detail="Only a seated booking can be finished")
    row.status = "finished"
    await _release_table_if_clear(db, tenant_id, row.table_id)
    await db.flush()
    return row


class _GuestLine:
    def __init__(self, product_id: str, quantity: float):
        self.product_id = product_id
        self.quantity = quantity
        self.unit_price = None
        self.modifier_ids: list[str] = []
        self.course = None


class _GuestOrder:
    def __init__(self, *, customer_name: str, notes: str | None, lines: list[_GuestLine]):
        self.service_mode = "takeaway"
        self.payment_method = "cash"
        self.store_id = None
        self.table_id = None
        self.customer_name = customer_name
        self.notes = notes
        self.delivery_address = None
        self.delivery_zone = None
        self.lines = lines


async def public_order_page(db: AsyncSession, slug: str) -> dict:
    tenant = await _restaurant_tenant(db, slug=slug)
    if not _online_orders_open(tenant):
        raise HTTPException(status_code=404, detail="Online food orders are closed")
    return {
        "slug": tenant.slug,
        "company_name": tenant.company_name,
        "path": f"/order/{tenant.slug}",
        "open": True,
        "menu": await list_public_menu(db, tenant.id),
    }


async def create_public_order(
    db: AsyncSession,
    slug: str,
    *,
    customer_name: str,
    notes: str | None,
    lines: list,
) -> m.RestaurantOrder:
    tenant = await _restaurant_tenant(db, slug=slug)
    if not _online_orders_open(tenant):
        raise HTTPException(status_code=404, detail="Online food orders are closed")
    name = require_honest_narrative(customer_name, label="customer name", min_length=1, max_length=180)
    if not lines or len(lines) > 8:
        raise HTTPException(status_code=422, detail="Choose from 1 to 8 menu items.")
    guest_lines: list[_GuestLine] = []
    for line in lines:
        product = await _product(db, tenant.id, line.product_id)
        if not await _is_public_menu_item(db, tenant.id, product):
            raise HTTPException(status_code=422, detail="Choose a menu item.")
        guest_lines.append(_GuestLine(product.id, line.quantity))
    order = await create_order(
        db,
        tenant.id,
        _GuestOrder(
            customer_name=name,
            notes=notes,
            lines=guest_lines,
        ),
        user_id=None,
    )
    order.notes = write_order_channel(order.notes)
    await db.flush()
    return order
