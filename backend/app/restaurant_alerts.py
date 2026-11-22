"""Alerts to the restaurant when a guest orders or books online: in-app, email, and WhatsApp.

Where the restaurant wants them is kept in the company settings (``restaurant_alerts``): a few email
addresses and one WhatsApp number. Sending never blocks or fails the guest's order or booking: it runs
after the reply, and every channel is tried on its own.

WhatsApp goes through the company's Twilio account (the same one used for SMS). Twilio only lets a
business start a WhatsApp chat with an approved template, so a template can be saved here; without one
the plain message works in Twilio's sandbox and inside a 24 hour reply window.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app import restaurant as rs
from app.config import settings

logger = logging.getLogger(__name__)

ALERTS_KEY = "restaurant_alerts"
MAX_EMAILS = 5
TEMPLATE_RE = re.compile(r"^HX[0-9A-Za-z]{32}$")
NOTIFY_ROLES = ["company_admin", "restaurant_manager"]

DEFAULTS: dict[str, Any] = {
    "emails": [],
    "whatsapp": None,
    "whatsapp_from": None,
    "whatsapp_template": None,
    "orders": True,
    "bookings": True,
    "email_on": True,
    "whatsapp_on": True,
}


def alerts_of(tenant: m.Tenant) -> dict:
    raw = getattr(tenant, "document_numbering", None) or {}
    saved = raw.get(ALERTS_KEY) if isinstance(raw, dict) else None
    out = {**DEFAULTS}
    if isinstance(saved, dict):
        out.update({k: v for k, v in saved.items() if k in DEFAULTS})
    return out


def recipients_of(tenant: m.Tenant, cfg: dict) -> list[str]:
    emails = [e for e in (cfg.get("emails") or []) if e]
    if not emails and getattr(tenant, "email", None):
        emails = [tenant.email]  # until they add addresses, the company email gets them
    return emails


def channel_status(tenant: m.Tenant) -> dict:
    from app import emailer
    from app import sms as sms_svc
    from app.email_settings import resolve_smtp_config
    from app.sms_settings import resolve_sms_config

    sms_cfg = resolve_sms_config(tenant)
    return {
        "email": emailer._delivery_mode(resolve_smtp_config(tenant)),
        "whatsapp": sms_svc._delivery_mode(sms_cfg),
        "whatsapp_ready": bool(sms_cfg.configured),
    }


def serialize(tenant: m.Tenant) -> dict:
    cfg = alerts_of(tenant)
    return {**cfg, "channels": channel_status(tenant), "company_email": getattr(tenant, "email", None)}


async def save_alerts(db: AsyncSession, tenant_id: str, payload, *, user_id: str | None) -> dict:
    tenant = await rs._restaurant_tenant(db, tenant_id=tenant_id)
    data = payload.model_dump(exclude_unset=True)
    cfg = alerts_of(tenant)
    if "emails" in data:
        seen: list[str] = []
        for email in data["emails"] or []:
            clean = str(email).strip().lower()
            if clean and clean not in seen:
                seen.append(clean)
        if len(seen) > MAX_EMAILS:
            raise HTTPException(status_code=422, detail=f"Add up to {MAX_EMAILS} email addresses.")
        cfg["emails"] = seen
    for field in ("whatsapp", "whatsapp_from"):
        if field in data:
            cfg[field] = data[field] or None
    if "whatsapp_template" in data:
        raw = (data["whatsapp_template"] or "").strip()
        if raw and not TEMPLATE_RE.match(raw):
            raise HTTPException(status_code=422, detail="That is not a Twilio template id. It starts with HX.")
        cfg["whatsapp_template"] = raw or None
    for field in ("orders", "bookings", "email_on", "whatsapp_on"):
        if data.get(field) is not None:
            cfg[field] = bool(data[field])
    doc = dict(tenant.document_numbering) if isinstance(tenant.document_numbering, dict) else {}
    doc[ALERTS_KEY] = cfg
    tenant.document_numbering = doc
    await db.flush()
    await audit_svc.record_event(
        db,
        tenant_id=tenant.id,
        user_id=user_id,
        module="restaurant",
        action="restaurant_alerts_saved",
        entity="restaurant_alerts",
        entity_id=tenant.id,
        details={"fields": sorted(data)},
    )
    return serialize(tenant)


def _money(tenant: m.Tenant, value) -> str:
    try:
        return f"{tenant.currency or 'GHS'} {float(value):,.2f}"
    except Exception:  # noqa: BLE001
        return f"{tenant.currency or 'GHS'} {value}"


def compose(tenant: m.Tenant, kind: str, info: dict) -> tuple[str, list[str], str]:
    """The headline, the detail lines, and the page to open for one new order or booking."""
    base = (settings.FRONTEND_URL or "http://localhost:3000").rstrip("/")
    if kind == "order":
        title = f"New online order {info.get('number') or ''}".strip()
        lines = [
            f"{'Delivery' if info.get('service') == 'delivery' else 'Pickup'} · {_money(tenant, info.get('total', 0))}",
            f"Guest: {info.get('name')} · {info.get('phone')}",
        ]
        if info.get("items"):
            lines.append("Items: " + info["items"])
        if info.get("address"):
            lines.append("Deliver to: " + info["address"])
        if info.get("ready_by"):
            lines.append("Ready by: " + str(info["ready_by"]))
        if info.get("allergy"):
            lines.append("ALLERGY: " + info["allergy"])
        if info.get("notes"):
            lines.append("Note: " + info["notes"])
        return title, lines, f"{base}/restaurant?tab=orders"
    title = "New table booking"
    lines = [
        f"{info.get('name')} · {info.get('phone')}",
        f"{info.get('party')} {'guest' if info.get('party') == 1 else 'guests'} · {info.get('when')}",
    ]
    if info.get("notes"):
        lines.append("Note: " + info["notes"])
    return title, lines, f"{base}/restaurant?tab=bookings"


async def deliver(tenant: m.Tenant, kind: str, info: dict, *, only_test: bool = False) -> dict:
    """Email and WhatsApp for one event. Each channel reports on its own; none raises."""
    from app import emailer
    from app import sms as sms_svc

    cfg = alerts_of(tenant)
    title, lines, link = compose(tenant, kind, info)
    if only_test:
        title = "Test: " + title
    result: dict[str, Any] = {}

    recipients = recipients_of(tenant, cfg)
    if cfg["email_on"] and recipients:
        try:
            inner = (
                f"<h3>{html.escape(title)}</h3>"
                + "".join(f"<p>{html.escape(line)}</p>" for line in lines)
                + f'<p><a href="{html.escape(link)}">Open it in the ERP</a></p>'
            )
            text = title + "\n\n" + "\n".join(lines) + f"\n\nOpen it: {link}\n"
            company = getattr(tenant, "company_name", None) or "RIBDIGI ERP"
            branded = emailer.render_branded_html(body_html=inner, company_name=company, tenant=tenant, title=title)
            sent = await emailer.send_email(to=recipients, subject=title, text_body=text, html_body=branded, tenant=tenant)
            result["email"] = {"sent": bool(sent.sent), "mode": sent.mode, "to": recipients, "error": getattr(sent, "error", None)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("restaurant alert email failed")
            result["email"] = {"sent": False, "error": str(exc)[:300]}
    elif cfg["email_on"]:
        result["email"] = {"sent": False, "error": "No email address yet."}

    if cfg["whatsapp_on"] and cfg.get("whatsapp"):
        try:
            body = title + "\n" + "\n".join(lines)
            sent = await sms_svc.send_whatsapp(
                to=cfg["whatsapp"],
                body=body,
                tenant=tenant,
                from_number=cfg.get("whatsapp_from"),
                template_sid=cfg.get("whatsapp_template"),
                variables={"1": title, "2": " | ".join(lines)[:900]},
            )
            result["whatsapp"] = {"sent": bool(sent.sent), "mode": sent.mode, "error": sent.error}
        except Exception as exc:  # noqa: BLE001
            logger.exception("restaurant alert whatsapp failed")
            result["whatsapp"] = {"sent": False, "error": str(exc)[:300]}
    return result


async def dispatch(tenant_id: str, kind: str, info: dict) -> None:
    """Runs after the guest has their answer: in-app note first, then email and WhatsApp."""
    from app import notifications
    from app.db import SessionLocal

    try:
        async with SessionLocal() as db:
            tenant = await db.get(m.Tenant, tenant_id)
            if tenant is None:
                return
            cfg = alerts_of(tenant)
            if not cfg["orders" if kind == "order" else "bookings"]:
                return
            title, lines, _link = compose(tenant, kind, info)
            try:
                await notifications.create_notification(
                    db,
                    tenant_id=tenant_id,
                    title=title,
                    message=" · ".join(lines)[:480],
                    category="new_order",
                    roles=NOTIFY_ROLES,
                    entity_type="restaurant_order" if kind == "order" else "restaurant_booking",
                    entity_id=info.get("id"),
                    send_email=False,
                )
                await db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("restaurant alert in-app note failed")
            await deliver(tenant, kind, info)
    except Exception:  # noqa: BLE001
        logger.exception("restaurant alert dispatch failed")


def order_info(order: m.RestaurantOrder, tracked: dict, *, name: str, phone: str, payload) -> dict:
    items = ", ".join(f"{int(i['quantity']) if float(i['quantity']).is_integer() else i['quantity']}× {i['name']}" for i in tracked.get("items", []))
    return {
        "id": order.id,
        "number": order.order_number,
        "service": tracked.get("service"),
        "total": tracked.get("total_amount"),
        "name": name,
        "phone": phone,
        "items": items,
        "address": getattr(payload, "delivery_address", None) if tracked.get("service") == "delivery" else None,
        "ready_by": getattr(payload, "ready_by", None),
        "allergy": getattr(payload, "allergy", None),
        "notes": getattr(payload, "notes", None),
    }


def booking_info(row: m.RestaurantBooking) -> dict:
    return {
        "id": row.id,
        "name": row.guest_name,
        "phone": row.phone,
        "party": row.party_size,
        "when": row.booked_for.strftime("%a %d %b, %H:%M") if getattr(row, "booked_for", None) else "",
        "notes": row.notes,
    }
