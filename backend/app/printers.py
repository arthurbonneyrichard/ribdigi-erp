"""Tenant printer routing, job queue, and secure print-agent pairing.

The browser cannot enumerate OS printers or silently fan-out. Destinations are:
- browser_dialog: cashier uses the OS print dialog / PDF (ack is explicit)
- print_agent: paired local agent polls jobs with a hashed token
- network: ESC/POS host/port stored after backend allowlist validation
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import secrets
import socket
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app import models as m
from app.honesty import require_honest_narrative
from app.security import hash_token

PURPOSES = frozenset({"customer_receipt", "invoice", "kitchen", "bar", "barcode"})
GENERAL_PURPOSES = frozenset({"customer_receipt", "invoice", "barcode"})
# Extra destinations keyed by saved Tenant.industry (canonical).
# Hotel is in the industry catalog but has no extra print destinations —
# do not invent restaurant kitchen/bar for hotel tenants.
INDUSTRY_PURPOSES: dict[str, frozenset[str]] = {
    "restaurant": frozenset({"kitchen", "bar"}),
}
CONNECTION_TYPES = frozenset({"browser_dialog", "print_agent", "network"})
PAPERS = frozenset({"58mm", "80mm", "a4"})
PREP_STATIONS = frozenset({"kitchen", "bar"})
JOB_STATUSES = frozenset(
    {"queued", "claimed", "printing", "printed", "failed", "cancelled", "browser_pending"}
)
TERMINAL_STATUSES = frozenset({"printed", "cancelled"})
MAX_ATTEMPTS = 8
PAIRING_TTL_MINUTES = 15
AGENT_TOKEN_PREFIX = "rdp_"

_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,253}$")


class PrinterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    connection_type: str = "browser_dialog"
    store_id: str | None = None
    agent_id: str | None = None
    paper: str = "80mm"
    purposes: list[str] = Field(default_factory=lambda: ["customer_receipt"])
    copies: int = Field(default=1, ge=1, le=9)
    is_enabled: bool = True
    is_default: bool = False
    host: str | None = None
    port: int = Field(default=9100, ge=1, le=65535)


class PrinterUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    connection_type: str | None = None
    store_id: str | None = None
    clear_store: bool = False
    agent_id: str | None = None
    clear_agent: bool = False
    paper: str | None = None
    purposes: list[str] | None = None
    copies: int | None = Field(default=None, ge=1, le=9)
    is_enabled: bool | None = None
    is_default: bool | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    clear_host: bool = False


class PairingCodeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=120)
    store_id: str | None = None


class AgentPairBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairing_code: str = Field(min_length=6, max_length=32)
    label: str | None = Field(default=None, max_length=120)


class JobCompleteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    detail: str | None = None


class ReprintBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = "pos_sale"
    source_id: str
    purposes: list[str] | None = None


class BrowserAckBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    detail: str | None = None


def _canonical_industry(industry: str | None) -> str | None:
    from app.packages import canonicalize_industry

    return canonicalize_industry(industry)


def purposes_for_industry(industry: str | None) -> list[str]:
    extra = INDUSTRY_PURPOSES.get(_canonical_industry(industry) or "", frozenset())
    return sorted(GENERAL_PURPOSES | extra)


def purpose_allowed_for_industry(purpose: str, industry: str | None) -> bool:
    return purpose in set(purposes_for_industry(industry))


def visible_purposes_for_industry(purposes: list[str] | None, industry: str | None) -> list[str]:
    """Purposes the operator may see/select for this saved industry.

    Leftover kitchen/bar rows stay in the DB; they are omitted from the list
    when none of their purposes apply (does not delete other tenants' printers).
    """
    allowed = set(purposes_for_industry(industry))
    return [p for p in (purposes or []) if p in allowed]


def printer_visible_for_industry(row: m.Printer, industry: str | None) -> bool:
    return bool(visible_purposes_for_industry(row.purposes, industry))


async def load_tenant_industry(
    db: AsyncSession, tenant_id: str, tenant: m.Tenant | None = None
) -> str | None:
    """Saved Tenant.industry only — never a UI-only or client-supplied value."""
    row = tenant if tenant is not None and getattr(tenant, "id", None) == tenant_id else await db.get(
        m.Tenant, tenant_id
    )
    return _canonical_industry(getattr(row, "industry", None) if row else None)


def normalize_purpose(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in PURPOSES:
        raise HTTPException(
            status_code=400,
            detail=f"purpose must be one of: {', '.join(sorted(PURPOSES))}",
        )
    return key


def normalize_purposes(values: list[str] | None, *, industry: str | None) -> list[str]:
    if not values:
        raise HTTPException(status_code=400, detail="Select at least one printer purpose")
    allowed = set(purposes_for_industry(industry))
    out: list[str] = []
    for raw in values:
        key = normalize_purpose(str(raw))
        if key not in allowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{key}' printers are not available for this business type. "
                    f"Allowed: {', '.join(sorted(allowed))}"
                ),
            )
        if key not in out:
            out.append(key)
    return out


def normalize_connection(value: str | None) -> str:
    key = (value or "browser_dialog").strip().lower()
    if key not in CONNECTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"connection_type must be one of: {', '.join(sorted(CONNECTION_TYPES))}",
        )
    return key


def normalize_paper(value: str | None) -> str:
    key = (value or "80mm").strip().lower()
    if key not in PAPERS:
        raise HTTPException(
            status_code=400, detail=f"paper must be one of: {', '.join(sorted(PAPERS))}"
        )
    return key


def normalize_prep_station(value: str | None, *, allow_empty: bool = True) -> str | None:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        if allow_empty:
            return None
        raise HTTPException(status_code=400, detail="prep_station cannot be blank")
    if key in {"none", "retail", "unset"}:
        return None
    if key not in PREP_STATIONS:
        raise HTTPException(
            status_code=400,
            detail="prep_station must be kitchen, bar, or empty for retail",
        )
    return key


def validate_network_host(host: str) -> str:
    """Allow only loopback, RFC1918, or .local names. Reject metadata / public IPs."""
    raw = require_honest_narrative(host, label="printer host", max_length=255).strip()
    if not _HOST_RE.match(raw):
        raise HTTPException(status_code=400, detail="printer host is not a valid hostname or IP")
    lowered = raw.lower()
    if lowered in {"localhost", "localhost.localdomain"}:
        return "127.0.0.1"
    try:
        ip = ipaddress.ip_address(raw)
    except ValueError:
        if lowered.endswith(".local"):
            return raw
        raise HTTPException(
            status_code=400,
            detail=(
                "Network printers must use a private IP, loopback, or .local name. "
                "Public hosts cannot be set from the API."
            ),
        ) from None
    if ip.is_loopback:
        return str(ip)
    if ip.is_private and not ip.is_link_local:
        return str(ip)
    raise HTTPException(
        status_code=400,
        detail="Network printer host must be a private (RFC1918) or loopback address",
    )


def pos_show_receipt_email_sms(tenant: m.Tenant | None) -> bool:
    """Company choice: Email/SMS receipt actions on the till. Default off."""
    raw = getattr(tenant, "print_branding", None) if tenant else None
    if not isinstance(raw, dict):
        return False
    return raw.get("pos_show_receipt_email_sms") is True


def set_pos_show_receipt_email_sms(tenant: m.Tenant, enabled: bool) -> bool:
    current = dict(getattr(tenant, "print_branding", None) or {})
    current["pos_show_receipt_email_sms"] = bool(enabled)
    tenant.print_branding = current
    flag_modified(tenant, "print_branding")
    return bool(enabled)


class ReceiptEmailSmsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    show_email_sms: bool


def capabilities(industry: str | None = None) -> dict[str, Any]:
    ind = _canonical_industry(industry)
    allowed = purposes_for_industry(ind)
    extra = sorted(INDUSTRY_PURPOSES.get(ind or "", frozenset()))
    prep = sorted(PREP_STATIONS) if extra else []
    return {
        "browser_enumerates_os_printers": False,
        "browser_silent_fanout": False,
        "fallback": "browser_print_dialog",
        "destinations": sorted(CONNECTION_TYPES),
        "industry": ind,
        "purposes": allowed,
        "industry_specific_purposes": extra,
        "papers": sorted(PAPERS),
        "prep_stations": prep,
        "printed_means": "agent_or_browser_ack_or_network_send_success",
        "queued_is_not_printed": True,
        "notes": (
            "The browser cannot list every OS printer. Pair a till print agent "
            "or register an allowlisted network printer. Checkout still completes "
            "if a printer is offline; receipt numbers are issued by the server. "
            "Kitchen and bar destinations are restaurant-only."
        ),
    }


async def drop_inapplicable_printer_destinations(
    db: AsyncSession, *, tenant_id: str, industry: str | None
) -> None:
    """Industry change: strip inapplicable purposes; disable printers with none left.

    Does not remap kitchen/bar onto receipt/invoice/barcode.
    Scoped to this tenant_id only.
    """
    allowed = set(purposes_for_industry(industry))
    rows = list(
        (
            await db.execute(select(m.Printer).where(m.Printer.tenant_id == tenant_id))
        ).scalars().all()
    )
    now = datetime.utcnow()
    for row in rows:
        current = [str(p) for p in (row.purposes or [])]
        kept = [p for p in current if p in allowed]
        if kept == current:
            continue
        row.purposes = kept
        if not kept:
            row.is_enabled = False
        row.updated_at = now


def serialize_agent(row: m.PrintAgent, *, include_secret: str | None = None) -> dict[str, Any]:
    data = {
        "id": row.id,
        "label": row.label,
        "store_id": row.store_id,
        "is_active": bool(row.is_active),
        "paired": bool(row.token_hash),
        "last_seen_at": row.last_seen_at,
        "created_at": row.created_at,
    }
    if include_secret:
        data["agent_token"] = include_secret
        data["secret_shown_once"] = True
    return data


def serialize_printer(row: m.Printer) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "connection_type": row.connection_type,
        "store_id": row.store_id,
        "agent_id": row.agent_id,
        "paper": row.paper,
        "purposes": list(row.purposes or []),
        "copies": int(row.copies or 1),
        "is_enabled": bool(row.is_enabled),
        "is_default": bool(row.is_default),
        "host": row.host if row.connection_type == "network" else None,
        "port": int(row.port or 9100) if row.connection_type == "network" else None,
        "status": row.status,
        "last_error": row.last_error,
        "last_seen_at": row.last_seen_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_job(row: m.PrintJob, *, include_payload: bool = False) -> dict[str, Any]:
    data = {
        "id": row.id,
        "printer_id": row.printer_id,
        "store_id": row.store_id,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "purpose": row.purpose,
        "status": row.status,
        "copies": int(row.copies or 1),
        "attempt_count": int(row.attempt_count or 0),
        "idempotency_key": row.idempotency_key,
        "reprint_of_job_id": row.reprint_of_job_id,
        "last_error": row.last_error,
        "printed_at": row.printed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "is_printed": row.status == "printed",
    }
    if include_payload:
        data["payload"] = row.payload or {}
    return data


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


def _initial_status(connection_type: str) -> str:
    if connection_type == "browser_dialog":
        return "browser_pending"
    return "queued"


async def _require_store(
    db: AsyncSession, tenant_id: str, store_id: str | None
) -> m.Store | None:
    if not store_id:
        return None
    store = await db.get(m.Store, store_id)
    if not store or store.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


async def assert_printer_store_access(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    role: str | None,
    store_id: str | None,
) -> None:
    from app import store_access as store_access_svc

    await store_access_svc.assert_store_access(
        db, tenant_id=tenant_id, user_id=user_id, store_id=store_id
    )


async def list_printers(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None = None,
    purpose: str | None = None,
) -> list[m.Printer]:
    stmt = select(m.Printer).where(m.Printer.tenant_id == tenant_id).order_by(m.Printer.name)
    if store_id:
        stmt = stmt.where(or_(m.Printer.store_id == store_id, m.Printer.store_id.is_(None)))
    rows = list((await db.execute(stmt)).scalars().all())
    industry = await load_tenant_industry(db, tenant_id)
    if purpose:
        want = normalize_purpose(purpose)
        if not purpose_allowed_for_industry(want, industry):
            return []
        rows = [r for r in rows if want in (r.purposes or [])]
    else:
        rows = [r for r in rows if printer_visible_for_industry(r, industry)]
    return rows


async def create_printer(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    payload: PrinterCreate,
) -> m.Printer:
    name = require_honest_narrative(payload.name, label="printer name", max_length=120)
    conn = normalize_connection(payload.connection_type)
    paper = normalize_paper(payload.paper)
    industry = await load_tenant_industry(db, tenant_id)
    purposes = normalize_purposes(payload.purposes, industry=industry)
    await _require_store(db, tenant_id, payload.store_id)
    host = None
    agent_id = payload.agent_id
    if conn == "network":
        if not payload.host:
            raise HTTPException(status_code=400, detail="host is required for network printers")
        host = validate_network_host(payload.host)
        agent_id = None
    elif conn == "print_agent":
        if not agent_id:
            raise HTTPException(status_code=400, detail="agent_id is required for print_agent printers")
        agent = await db.get(m.PrintAgent, agent_id)
        if not agent or agent.tenant_id != tenant_id or not agent.is_active:
            raise HTTPException(status_code=404, detail="Print agent not found")
        host = None
    else:
        agent_id = None
        host = None
    dup = (
        await db.execute(
            select(m.Printer).where(m.Printer.tenant_id == tenant_id, m.Printer.name == name)
        )
    ).scalar_one_or_none()
    if dup:
        raise HTTPException(status_code=409, detail="A printer with this name already exists")
    row = m.Printer(
        tenant_id=tenant_id,
        store_id=payload.store_id,
        agent_id=agent_id,
        name=name,
        connection_type=conn,
        paper=paper,
        purposes=purposes,
        copies=int(payload.copies or 1),
        is_enabled=bool(payload.is_enabled),
        is_default=bool(payload.is_default),
        host=host,
        port=int(payload.port or 9100),
        status="online" if conn == "browser_dialog" else "unknown",
        created_by=user_id,
    )
    db.add(row)
    await db.flush()
    if row.is_default:
        await _clear_other_defaults(db, row)
    return row


async def update_printer(
    db: AsyncSession,
    *,
    tenant_id: str,
    printer_id: str,
    payload: PrinterUpdate,
) -> m.Printer:
    row = await db.get(m.Printer, printer_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Printer not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and payload.name is not None:
        name = require_honest_narrative(payload.name, label="printer name", max_length=120)
        clash = (
            await db.execute(
                select(m.Printer).where(
                    m.Printer.tenant_id == tenant_id,
                    m.Printer.name == name,
                    m.Printer.id != row.id,
                )
            )
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="A printer with this name already exists")
        row.name = name
    if payload.connection_type is not None:
        row.connection_type = normalize_connection(payload.connection_type)
    if payload.paper is not None:
        row.paper = normalize_paper(payload.paper)
    if payload.purposes is not None:
        industry = await load_tenant_industry(db, tenant_id)
        row.purposes = normalize_purposes(payload.purposes, industry=industry)
    if payload.copies is not None:
        row.copies = int(payload.copies)
    if payload.is_enabled is not None:
        row.is_enabled = bool(payload.is_enabled)
    if payload.is_default is not None:
        row.is_default = bool(payload.is_default)
    if payload.clear_store:
        row.store_id = None
    elif payload.store_id is not None:
        await _require_store(db, tenant_id, payload.store_id)
        row.store_id = payload.store_id
    if payload.clear_agent:
        row.agent_id = None
    elif payload.agent_id is not None:
        agent = await db.get(m.PrintAgent, payload.agent_id)
        if not agent or agent.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Print agent not found")
        row.agent_id = agent.id
    if payload.clear_host:
        row.host = None
    elif payload.host is not None:
        row.host = validate_network_host(payload.host)
    if payload.port is not None:
        row.port = int(payload.port)
    if row.connection_type == "network" and not row.host:
        raise HTTPException(status_code=400, detail="host is required for network printers")
    if row.connection_type == "print_agent" and not row.agent_id:
        raise HTTPException(status_code=400, detail="agent_id is required for print_agent printers")
    if row.connection_type != "network":
        row.host = None
    if row.connection_type != "print_agent":
        row.agent_id = None
    row.updated_at = datetime.utcnow()
    await db.flush()
    if row.is_default:
        await _clear_other_defaults(db, row)
    return row


async def _clear_other_defaults(db: AsyncSession, row: m.Printer) -> None:
    others = (
        await db.execute(
            select(m.Printer).where(
                m.Printer.tenant_id == row.tenant_id,
                m.Printer.id != row.id,
                m.Printer.is_default.is_(True),
            )
        )
    ).scalars().all()
    for other in others:
        overlap = set(other.purposes or []) & set(row.purposes or [])
        same_store = (other.store_id or "") == (row.store_id or "")
        if overlap and same_store:
            other.is_default = False


async def issue_pairing_code(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str | None,
    payload: PairingCodeCreate,
) -> tuple[m.PrintAgent, str]:
    label = require_honest_narrative(payload.label, label="agent label", max_length=120)
    await _require_store(db, tenant_id, payload.store_id)
    raw = secrets.token_hex(4).upper()
    agent = m.PrintAgent(
        tenant_id=tenant_id,
        store_id=payload.store_id,
        label=label,
        pairing_code_hash=hash_token(raw),
        pairing_expires_at=datetime.utcnow() + timedelta(minutes=PAIRING_TTL_MINUTES),
        created_by=user_id,
        is_active=True,
    )
    db.add(agent)
    await db.flush()
    return agent, raw


async def pair_agent(db: AsyncSession, *, pairing_code: str, label: str | None) -> tuple[m.PrintAgent, str]:
    code = (pairing_code or "").strip().upper()
    if len(code) < 6:
        raise HTTPException(status_code=400, detail="Invalid pairing code")
    digest = hash_token(code)
    now = datetime.utcnow()
    agent = (
        await db.execute(
            select(m.PrintAgent).where(
                m.PrintAgent.pairing_code_hash == digest,
                m.PrintAgent.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not agent or not agent.pairing_expires_at or agent.pairing_expires_at < now:
        raise HTTPException(status_code=400, detail="Pairing code is invalid or expired")
    if agent.token_hash:
        raise HTTPException(status_code=409, detail="This agent is already paired")
    token = AGENT_TOKEN_PREFIX + secrets.token_urlsafe(32)
    agent.token_hash = hash_token(token)
    agent.pairing_code_hash = None
    agent.pairing_expires_at = None
    agent.last_seen_at = now
    if label:
        agent.label = require_honest_narrative(label, label="agent label", max_length=120)
    agent.updated_at = now
    await db.flush()
    return agent, token


async def authenticate_agent(db: AsyncSession, raw_token: str) -> m.PrintAgent:
    token = (raw_token or "").strip()
    if not token.startswith(AGENT_TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid print agent token")
    agent = (
        await db.execute(
            select(m.PrintAgent).where(
                m.PrintAgent.token_hash == hash_token(token),
                m.PrintAgent.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid print agent token")
    agent.last_seen_at = datetime.utcnow()
    return agent


def _idempotency_key(
    *,
    source_type: str,
    source_id: str,
    purpose: str,
    printer_id: str,
    reprint_seq: int = 0,
) -> str:
    if reprint_seq:
        return f"{source_type}:{source_id}:{purpose}:{printer_id}:reprint:{reprint_seq}"
    return f"{source_type}:{source_id}:{purpose}:{printer_id}"


def render_prep_ticket(
    *,
    reference: str,
    station: str,
    items: list[dict[str, Any]],
    store_name: str | None,
    paper: str = "80mm",
) -> str:
    from app.receipts import THERMAL_WIDTHS, _center, _wrap

    width = THERMAL_WIDTHS.get(paper, THERMAL_WIDTHS["80mm"])
    lines = [
        _center((store_name or "RIBDIGI").upper(), width),
        _center(f"{station.upper()} TICKET", width),
        _center(f"Order {reference}", width),
        "-" * width,
    ]
    for item in items:
        qty = item.get("quantity") or 0
        name = str(item.get("name") or "Item")
        for wrapped in _wrap(f"{qty:g} x {name}", width):
            lines.append(wrapped)
        note = item.get("notes")
        if note:
            for wrapped in _wrap(f"  {note}", width):
                lines.append(wrapped)
    lines.append("-" * width)
    lines.append(_center("Kitchen / bar copy only", width))
    lines.append("")
    return "\n".join(lines)


def _line_station(product: m.Product | None, category: m.ProductCategory | None) -> str | None:
    if product is not None:
        raw = getattr(product, "prep_station", None)
        if raw:
            return normalize_prep_station(raw)
    if category is not None:
        raw = getattr(category, "prep_station", None)
        if raw:
            return normalize_prep_station(raw)
    return None


async def matching_printers(
    db: AsyncSession,
    *,
    tenant_id: str,
    store_id: str | None,
    purpose: str,
    industry: str | None = None,
) -> list[m.Printer]:
    if industry is None:
        industry = await load_tenant_industry(db, tenant_id)
    if not purpose_allowed_for_industry(purpose, industry):
        return []
    rows = await list_printers(db, tenant_id=tenant_id, store_id=store_id, purpose=purpose)
    enabled = [r for r in rows if r.is_enabled]
    if store_id:
        scoped = [r for r in enabled if r.store_id == store_id]
        if scoped:
            return scoped
    return enabled


async def _record_attempt(
    db: AsyncSession,
    job: m.PrintJob,
    *,
    status: str,
    detail: str | None = None,
    actor_id: str | None = None,
) -> None:
    db.add(
        m.PrintJobAttempt(
            tenant_id=job.tenant_id,
            job_id=job.id,
            status=status,
            detail=detail,
            actor_id=actor_id,
        )
    )


def escpos_receipt_bytes(text: str) -> bytes:
    """ESC/POS slip: init, double-height type, text, feed, cut."""
    body = (text or "").replace("\r\n", "\n").replace("\n", "\r\n")
    encoded = body.encode("cp437", errors="replace")
    # Normal font (no double-height) so each padded line stays on the paper.
    return b"\x1b\x40" + b"\x1b\x61\x00" + encoded + b"\r\n\r\n\r\n" + b"\x1d\x56\x00"


def send_network_receipt(host: str, port: int, text: str) -> None:
    """Send one receipt to an allowlisted private printer. Raises on failure."""
    safe_host = validate_network_host(host)
    payload = escpos_receipt_bytes(text)
    with socket.create_connection((safe_host, int(port or 9100)), timeout=3) as sock:
        sock.sendall(payload)


async def _deliver_network_job(db: AsyncSession, printer: m.Printer, job: m.PrintJob) -> None:
    """Print a network job now. A failed send does not fail the sale."""
    if printer.connection_type != "network" or not printer.host:
        return
    text = ""
    if isinstance(job.payload, dict):
        text = str(job.payload.get("text") or "")
    if not text:
        return
    copies = max(1, int(printer.copies or 1))
    try:
        for _ in range(copies):
            await asyncio.to_thread(
                send_network_receipt, str(printer.host), int(printer.port or 9100), text
            )
    except Exception:
        logger.exception("Network receipt send failed printer_id=%s", printer.id)
        now = datetime.utcnow()
        job.status = "failed"
        job.last_error = "Could not reach the printer"
        printer.status = "error"
        printer.last_error = "Could not reach the printer"
        printer.updated_at = now
        await _record_attempt(db, job, status="failed", detail="network send failed")
        return
    now = datetime.utcnow()
    job.status = "printed"
    job.printed_at = now
    job.last_error = None
    printer.status = "online"
    printer.last_error = None
    printer.last_seen_at = now
    printer.updated_at = now
    await _record_attempt(db, job, status="printed", detail="sent to printer")


async def enqueue_job(
    db: AsyncSession,
    *,
    tenant_id: str,
    printer: m.Printer,
    source_type: str,
    source_id: str,
    purpose: str,
    payload: dict[str, Any],
    user_id: str | None,
    reprint_of_job_id: str | None = None,
    reprint_seq: int = 0,
    industry: str | None = None,
) -> m.PrintJob:
    if industry is None:
        industry = await load_tenant_industry(db, tenant_id)
    if not purpose_allowed_for_industry(purpose, industry):
        raise HTTPException(
            status_code=400,
            detail=f"'{purpose}' printers are not available for this business type",
        )
    key = _idempotency_key(
        source_type=source_type,
        source_id=source_id,
        purpose=purpose,
        printer_id=printer.id,
        reprint_seq=reprint_seq,
    )
    existing = (
        await db.execute(
            select(m.PrintJob).where(
                m.PrintJob.tenant_id == tenant_id,
                m.PrintJob.idempotency_key == key,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    status = _initial_status(printer.connection_type)
    job = m.PrintJob(
        tenant_id=tenant_id,
        printer_id=printer.id,
        store_id=printer.store_id,
        source_type=source_type,
        source_id=source_id,
        purpose=purpose,
        status=status,
        copies=int(printer.copies or 1),
        idempotency_key=key,
        reprint_of_job_id=reprint_of_job_id,
        payload=_jsonable(payload),
        created_by=user_id,
    )
    db.add(job)
    try:
        await db.flush()
    except IntegrityError:
        await db.refresh(printer)
        existing = (
            await db.execute(
                select(m.PrintJob).where(
                    m.PrintJob.tenant_id == tenant_id,
                    m.PrintJob.idempotency_key == key,
                )
            )
        ).scalar_one_or_none()
        if existing:
            return existing
        raise
    await _record_attempt(db, job, status=status, detail="enqueued", actor_id=user_id)
    await _deliver_network_job(db, printer, job)
    return job


async def enqueue_pos_sale_prints(
    db: AsyncSession,
    *,
    tenant_id: str,
    tx: m.Transaction,
    user_id: str | None,
    store_id: str | None,
    tenant: m.Tenant | None = None,
    store: m.Store | None = None,
) -> list[m.PrintJob]:
    """Fan-out jobs for one completed sale. Never creates another sale."""
    jobs: list[m.PrintJob] = []
    from app import receipts as receipts_svc

    industry = await load_tenant_industry(db, tenant_id, tenant)
    party = await receipts_svc.load_sale_party(
        db, tenant_id=tenant_id, party_id=getattr(tx, "party_id", None)
    )
    receipt = receipts_svc.build_receipt_payload(
        tx=tx, tenant=tenant, store=store, cashier_name=None, party=party
    )
    paper_default = receipt.get("default_receipt_paper") or "80mm"
    receipt_text = receipts_svc.render_thermal_text(receipt, paper=paper_default)
    receipt_html = receipts_svc.render_thermal_html(receipt, paper=paper_default)
    receipt_printers = await matching_printers(
        db, tenant_id=tenant_id, store_id=store_id, purpose="customer_receipt", industry=industry
    )
    for printer in receipt_printers:
        paper = printer.paper if printer.paper in {"58mm", "80mm"} else "80mm"
        payload = {
            "kind": "customer_receipt",
            "reference": tx.reference,
            "sale_id": tx.id,
            "text": receipts_svc.render_thermal_text(receipt, paper=paper),
            "html": receipts_svc.render_thermal_html(receipt, paper=paper),
            "receipt": {k: v for k, v in receipt.items() if k != "logo_key"},
            "browser_fallback": printer.connection_type == "browser_dialog",
            "payments_included": True,
        }
        jobs.append(
            await enqueue_job(
                db,
                tenant_id=tenant_id,
                printer=printer,
                source_type="pos_sale",
                source_id=tx.id,
                purpose="customer_receipt",
                payload=payload,
                user_id=user_id,
            )
        )

    items = list((tx.payload or {}).get("items") or [])
    if not (
        purpose_allowed_for_industry("kitchen", industry)
        or purpose_allowed_for_industry("bar", industry)
    ):
        _ = (receipt_text, receipt_html)
        return jobs

    product_ids = [i.get("product_id") for i in items if i.get("product_id")]
    products: dict[str, m.Product] = {}
    if product_ids:
        rows = (
            await db.execute(
                select(m.Product).where(
                    m.Product.tenant_id == tenant_id, m.Product.id.in_(product_ids)
                )
            )
        ).scalars().all()
        products = {p.id: p for p in rows}
    category_ids = {p.category_id for p in products.values() if p.category_id}
    categories: dict[str, m.ProductCategory] = {}
    if category_ids:
        cats = (
            await db.execute(
                select(m.ProductCategory).where(
                    m.ProductCategory.tenant_id == tenant_id,
                    m.ProductCategory.id.in_(category_ids),
                )
            )
        ).scalars().all()
        categories = {c.id: c for c in cats}

    by_station: dict[str, list[dict[str, Any]]] = {"kitchen": [], "bar": []}
    for raw in items:
        product = products.get(str(raw.get("product_id") or ""))
        category = categories.get(product.category_id) if product and product.category_id else None
        station = _line_station(product, category)
        if station in by_station:
            by_station[station].append(
                {
                    "name": raw.get("name") or (product.name if product else "Item"),
                    "quantity": raw.get("quantity"),
                    "sku": raw.get("sku"),
                    "product_id": raw.get("product_id"),
                    "notes": raw.get("notes"),
                }
            )

    for station, station_items in by_station.items():
        if not station_items:
            continue
        purpose = station
        for printer in await matching_printers(
            db, tenant_id=tenant_id, store_id=store_id, purpose=purpose, industry=industry
        ):
            paper = printer.paper if printer.paper in {"58mm", "80mm"} else "80mm"
            text = render_prep_ticket(
                reference=tx.reference,
                station=station,
                items=station_items,
                store_name=store.name if store else None,
                paper=paper,
            )
            payload = {
                "kind": "prep_ticket",
                "station": station,
                "reference": tx.reference,
                "sale_id": tx.id,
                "text": text,
                "items": station_items,
                "payments_included": False,
                "browser_fallback": printer.connection_type == "browser_dialog",
            }
            jobs.append(
                await enqueue_job(
                    db,
                    tenant_id=tenant_id,
                    printer=printer,
                    source_type="pos_sale",
                    source_id=tx.id,
                    purpose=purpose,
                    payload=payload,
                    user_id=user_id,
                )
            )
    _ = (receipt_text, receipt_html)
    return jobs


async def enqueue_invoice_prints(
    db: AsyncSession,
    *,
    tenant_id: str,
    invoice: m.SalesInvoice,
    user_id: str | None,
    text: str,
) -> list[m.PrintJob]:
    jobs: list[m.PrintJob] = []
    industry = await load_tenant_industry(db, tenant_id)
    printers = await matching_printers(
        db, tenant_id=tenant_id, store_id=invoice.store_id, purpose="invoice", industry=industry
    )
    for printer in printers:
        payload = {
            "kind": "invoice",
            "invoice_id": invoice.id,
            "reference": invoice.invoice_number,
            "text": text,
            "browser_fallback": printer.connection_type == "browser_dialog",
        }
        jobs.append(
            await enqueue_job(
                db,
                tenant_id=tenant_id,
                printer=printer,
                source_type="sales_invoice",
                source_id=invoice.id,
                purpose="invoice",
                payload=payload,
                user_id=user_id,
            )
        )
    return jobs


async def enqueue_test_print(
    db: AsyncSession,
    *,
    tenant_id: str,
    printer: m.Printer,
    user_id: str | None,
) -> m.PrintJob:
    payload = {
        "kind": "test",
        "text": f"RIBDIGI test print\n{printer.name}\nThis is not a sale.\n",
        "payments_included": False,
        "browser_fallback": printer.connection_type == "browser_dialog",
    }
    # source_id is varchar(36). A printer id plus a timestamp does not fit.
    key_source = m.uid()
    industry = await load_tenant_industry(db, tenant_id)
    purpose = next(
        (p for p in (printer.purposes or []) if purpose_allowed_for_industry(p, industry)),
        "customer_receipt",
    )
    return await enqueue_job(
        db,
        tenant_id=tenant_id,
        printer=printer,
        source_type="test",
        source_id=key_source,
        purpose=purpose,
        payload=payload,
        user_id=user_id,
        industry=industry,
    )


async def retry_job(
    db: AsyncSession,
    *,
    tenant_id: str,
    job_id: str,
    user_id: str | None,
) -> m.PrintJob:
    job = await db.get(m.PrintJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Print job not found")
    if job.status == "printed":
        raise HTTPException(status_code=409, detail="Job is already printed; use reprint")
    if int(job.attempt_count or 0) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=409, detail="Print job exceeded retry limit")
    printer = await db.get(m.Printer, job.printer_id)
    job.status = _initial_status(printer.connection_type if printer else "print_agent")
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.last_error = None
    job.claimed_by_agent_id = None
    job.claimed_at = None
    job.updated_at = datetime.utcnow()
    await _record_attempt(db, job, status="retry", detail="manual retry", actor_id=user_id)
    await db.flush()
    return job


async def reprint_source(
    db: AsyncSession,
    *,
    tenant_id: str,
    source_type: str,
    source_id: str,
    purposes: list[str] | None,
    user_id: str | None,
) -> list[m.PrintJob]:
    prior = (
        await db.execute(
            select(m.PrintJob).where(
                m.PrintJob.tenant_id == tenant_id,
                m.PrintJob.source_type == source_type,
                m.PrintJob.source_id == source_id,
            )
        )
    ).scalars().all()
    if not prior:
        raise HTTPException(status_code=404, detail="No print jobs for this document")
    industry = await load_tenant_industry(db, tenant_id)
    want = {normalize_purpose(p) for p in purposes} if purposes else {j.purpose for j in prior}
    if purposes:
        bad = sorted(p for p in want if not purpose_allowed_for_industry(p, industry))
        if bad:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Print destinations not available for this business type: "
                    + ", ".join(bad)
                ),
            )
    want = {p for p in want if purpose_allowed_for_industry(p, industry)}
    reprints: list[m.PrintJob] = []
    for purpose in want:
        originals = [j for j in prior if j.purpose == purpose]
        if not originals:
            continue
        seq = 1 + sum(1 for j in prior if j.purpose == purpose and j.reprint_of_job_id)
        for original in originals:
            printer = await db.get(m.Printer, original.printer_id)
            if not printer or not printer.is_enabled:
                continue
            reprints.append(
                await enqueue_job(
                    db,
                    tenant_id=tenant_id,
                    printer=printer,
                    source_type=source_type,
                    source_id=source_id,
                    purpose=purpose,
                    payload=dict(original.payload or {}),
                    user_id=user_id,
                    reprint_of_job_id=original.id,
                    reprint_seq=seq,
                )
            )
    return reprints


async def ack_browser_job(
    db: AsyncSession,
    *,
    tenant_id: str,
    job_id: str,
    status: str,
    user_id: str | None,
    detail: str | None = None,
) -> m.PrintJob:
    job = await db.get(m.PrintJob, job_id)
    if not job or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Print job not found")
    wanted = (status or "").strip().lower()
    if wanted not in {"printed", "failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="status must be printed, failed, or cancelled")
    return await complete_job(
        db, job=job, status=wanted, detail=detail, actor_id=user_id, agent=None
    )


async def complete_job(
    db: AsyncSession,
    *,
    job: m.PrintJob,
    status: str,
    detail: str | None,
    actor_id: str | None,
    agent: m.PrintAgent | None,
) -> m.PrintJob:
    wanted = (status or "").strip().lower()
    if wanted not in {"printed", "failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="status must be printed, failed, or cancelled")
    if job.status == "printed" and wanted == "printed":
        return job
    job.status = wanted
    job.last_error = detail if wanted != "printed" else None
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.updated_at = datetime.utcnow()
    if wanted == "printed":
        job.printed_at = datetime.utcnow()
        printer = await db.get(m.Printer, job.printer_id)
        if printer and (agent or printer.connection_type == "browser_dialog"):
            printer.status = "online"
            printer.last_seen_at = datetime.utcnow()
            printer.last_error = None
    elif wanted == "failed" and agent:
        printer = await db.get(m.Printer, job.printer_id)
        if printer:
            printer.status = "error"
            printer.last_error = detail
    await _record_attempt(db, job, status=wanted, detail=detail, actor_id=actor_id)
    await db.flush()
    return job


async def claim_jobs(
    db: AsyncSession, *, agent: m.PrintAgent, limit: int = 10
) -> list[m.PrintJob]:
    stmt = (
        select(m.PrintJob)
        .join(m.Printer, m.Printer.id == m.PrintJob.printer_id)
        .where(
            m.PrintJob.tenant_id == agent.tenant_id,
            m.PrintJob.status == "queued",
            m.Printer.connection_type == "print_agent",
            m.Printer.agent_id == agent.id,
            m.Printer.is_enabled.is_(True),
        )
        .order_by(m.PrintJob.created_at.asc())
        .limit(min(limit, 50))
    )
    if agent.store_id:
        stmt = stmt.where(
            or_(m.PrintJob.store_id == agent.store_id, m.PrintJob.store_id.is_(None))
        )
    rows = list((await db.execute(stmt)).scalars().all())
    now = datetime.utcnow()
    for job in rows:
        job.status = "claimed"
        job.claimed_by_agent_id = agent.id
        job.claimed_at = now
        job.updated_at = now
        await _record_attempt(db, job, status="claimed", actor_id=None)
    await db.flush()
    return rows


async def list_jobs(
    db: AsyncSession,
    *,
    tenant_id: str,
    source_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[m.PrintJob]:
    stmt = (
        select(m.PrintJob)
        .where(m.PrintJob.tenant_id == tenant_id)
        .order_by(m.PrintJob.created_at.desc())
        .limit(min(limit, 200))
    )
    if source_id:
        stmt = stmt.where(m.PrintJob.source_id == source_id)
    if status:
        wanted = status.strip().lower()
        if wanted not in JOB_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid job status filter")
        stmt = stmt.where(m.PrintJob.status == wanted)
    return list((await db.execute(stmt)).scalars().all())
