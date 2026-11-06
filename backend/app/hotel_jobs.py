"""Hotel staff roles do one job each.

The `hotel` module grant lets a role onto the desk. These lists decide what it may do
there, so a housekeeper cannot take a payment and a front-desk clerk cannot change
hotel settings. Refunds, voids and settings stay with the cashier or manager as listed.
Roles not listed here (hotel_manager, company admins) are decided by their module grant.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

_ID = r"[^/]+"

_ROOM_CARE = (
    r"POST /housekeeping",
    rf"POST /housekeeping/{_ID}/complete",
    r"POST /maintenance",
    rf"POST /maintenance/{_ID}/complete",
    r"POST /lost-found",
    rf"POST /lost-found/{_ID}/close",
    rf"POST /guest-requests/{_ID}/complete",
)
_BOOKING = (
    r"POST /guests",
    rf"PATCH /guests/{_ID}",
    r"POST /reservations",
    r"POST /reservation-groups",
    rf"PATCH /reservations/{_ID}",
    rf"POST /reservations/{_ID}/(confirm|cancel|duplicate|extend|move)",
    r"POST /guest-requests",
    rf"POST /guest-requests/{_ID}/complete",
    rf"POST /reservations/{_ID}/confirmation/send",
    r"POST /events",
    rf"POST /events/{_ID}/(confirm|cancel)",
)
_TAKING_MONEY = (
    rf"PATCH /folios/{_ID}",
    rf"POST /folios/{_ID}/(charges|payments|timing-fee|service-charge|service-charges)",
    rf"POST /folios/{_ID}/charges/{_ID}/transfer",
    rf"POST /folios/{_ID}/send",
    rf"POST /reservations/{_ID}/(check-in|check-out|leave-early|no-show|no-show-fee)",
    rf"POST /invoices/{_ID}/payments",
    r"POST /shop/sales",
    r"POST /cashier/shift/(open|close)",
)
_CORRECTING_MONEY = (
    rf"POST /folios/{_ID}/charges/{_ID}/void",
    rf"POST /folios/{_ID}/payments/{_ID}/refund",
    rf"POST /shop/sales/{_ID}/refund",
    rf"POST /reservations/{_ID}/deposit",
    rf"POST /reservations/{_ID}/close-bill",
    r"POST /night-audits",
)

_WRITES: dict[str, tuple[str, ...]] = {
    "hotel_housekeeping": _ROOM_CARE,
    "hotel_maintenance": _ROOM_CARE,
    "hotel_reservations": _BOOKING,
    "hotel_front_desk": _BOOKING + _TAKING_MONEY + _ROOM_CARE,
    "hotel_cashier": _TAKING_MONEY + _CORRECTING_MONEY,
}

_MONEY_PAGES = (
    r"/(reports|folios|invoices|cashier|night-audits|shop|deposits)(/.*)?"
    r"|/reservations/[^/]+/(folio|confirmation|print)"
    r"|/guests(/.*)?"  # ID numbers, phones and bills: nothing a room job needs
)
_READS_REFUSED: dict[str, str] = {
    "hotel_housekeeping": _MONEY_PAGES,
    "hotel_maintenance": _MONEY_PAGES,
    "hotel_reservations": r"/reports(/.*)?|/cashier(/.*)?|/night-audits",
    "hotel_front_desk": r"/reports(/.*)?",
}

_WORDS = {
    "hotel_housekeeping": "Housekeeping looks after rooms. Bills, payments and settings need the front desk or a manager.",
    "hotel_maintenance": "Maintenance looks after rooms. Bills, payments and settings need the front desk or a manager.",
    "hotel_reservations": "Reservations books stays. Check-in, payments and settings need the front desk or a manager.",
    "hotel_front_desk": "The front desk checks guests in and out and takes payment. Refunds, voids and settings need a cashier or manager.",
    "hotel_cashier": "The cashier handles bills and payments. Rooms, rates and settings need a manager.",
}

NO_MONEY_ROLES = frozenset({"hotel_housekeeping", "hotel_maintenance"})


def enforce(role: str | None, method: str, url_path: str) -> None:
    """Raise 403 when this hotel role may not make this request."""
    key = str(role or "")
    if key not in _WRITES:
        return
    path = url_path.split("/hotel", 1)[-1].rstrip("/") or "/"
    if method in {"GET", "HEAD", "OPTIONS"}:
        refused = _READS_REFUSED.get(key)
        if not refused or not re.fullmatch(refused, path):
            return
    elif any(re.fullmatch(rule, f"{method} {path}") for rule in _WRITES[key]):
        return
    raise HTTPException(status_code=403, detail={"code": "HOTEL_ROLE_JOB", "message": _WORDS[key]})
