"""CSV export for auth sessions, passkeys, and document settings (Stage 128). Secrets excluded."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import webauthn_svc as webauthn
from app.document_numbering import normalize_document_numbering, preview_document_numbering, DOC_KEYS

SESSION_EXPORT_COLUMNS = [
    "id",
    "status",
    "current",
    "ip_address",
    "user_agent",
    "expires_at",
    "revoked_at",
    "created_at",
]

PASSKEY_EXPORT_COLUMNS = [
    "name",
    "device_type",
    "backed_up",
    "sign_count",
    "transports",
    "created_at",
    "last_used_at",
]

DOCUMENT_SETTINGS_EXPORT_COLUMNS = [
    "section",
    "key",
    "prefix",
    "include_year",
    "pad",
    "next_number",
    "preview",
    "value",
]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value)


def session_status(row: m.AuthSession) -> str:
    return "revoked" if row.revoked_at is not None else "active"


def serialize_session(row: m.AuthSession, *, current_jti: str | None = None) -> dict:
    return {
        "id": row.id,
        "jti": row.jti,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "expires_at": row.expires_at,
        "revoked_at": row.revoked_at,
        "created_at": row.created_at,
        "status": session_status(row),
        "current": bool(current_jti) and row.jti == current_jti,
    }


async def list_user_sessions(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    status: str | None = None,
    active_only: bool = False,
) -> list[m.AuthSession]:
    """List the caller's sessions. Default (no status / active_only) = active only."""
    q = select(m.AuthSession).where(
        m.AuthSession.tenant_id == tenant_id,
        m.AuthSession.user_id == user_id,
    )
    status_n = (status or "").strip().lower() or None
    if status_n == "revoked":
        q = q.where(m.AuthSession.revoked_at.is_not(None))
    elif status_n == "active" or active_only:
        q = q.where(m.AuthSession.revoked_at.is_(None))
    elif status_n == "all":
        pass
    else:
        # Backward-compatible default: active (non-revoked) only
        q = q.where(m.AuthSession.revoked_at.is_(None))
    q = q.order_by(m.AuthSession.created_at.desc())
    return list((await db.execute(q)).scalars().all())


async def export_sessions_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
    current_jti: str | None = None,
    status: str | None = None,
    active_only: bool = False,
) -> str:
    rows = await list_user_sessions(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        status=status,
        active_only=active_only,
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=SESSION_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = serialize_session(row, current_jti=current_jti)
        writer.writerow(
            {
                "id": _cell(data.get("id")),
                "status": _cell(data.get("status")),
                "current": _cell(data.get("current")),
                "ip_address": _cell(data.get("ip_address")),
                "user_agent": _cell(data.get("user_agent")),
                "expires_at": _cell(data.get("expires_at")),
                "revoked_at": _cell(data.get("revoked_at")),
                "created_at": _cell(data.get("created_at")),
            }
        )
    return buf.getvalue()


async def export_passkeys_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    user_id: str,
) -> str:
    rows = await webauthn.list_credentials(db, tenant_id=tenant_id, user_id=user_id)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PASSKEY_EXPORT_COLUMNS)
    writer.writeheader()
    for row in rows:
        data = webauthn.serialize_credential(row)
        writer.writerow(
            {
                "name": _cell(data.get("name")),
                "device_type": _cell(data.get("device_type")),
                "backed_up": _cell(data.get("backed_up")),
                "sign_count": _cell(data.get("sign_count")),
                "transports": _cell(data.get("transports")),
                "created_at": _cell(data.get("created_at")),
                "last_used_at": _cell(data.get("last_used_at")),
            }
        )
    return buf.getvalue()


async def export_document_settings_csv(
    db: AsyncSession,
    *,
    tenant_id: str,
    company_id: str | None = None,
) -> str:
    from app.document_numbering import numbering_source_for_serialize

    tenant = (
        await db.execute(select(m.Tenant).where(m.Tenant.id == tenant_id))
    ).scalar_one()
    company = None
    if company_id:
        company = await db.get(m.Company, company_id)
        if not company or company.tenant_id != tenant_id:
            company = None
    raw = numbering_source_for_serialize(tenant, company)
    numbering = normalize_document_numbering(raw)
    previews = preview_document_numbering(raw)
    from app.print_branding import print_templates_for_serialize

    print_tpl = print_templates_for_serialize(tenant, company)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=DOCUMENT_SETTINGS_EXPORT_COLUMNS)
    writer.writeheader()
    for key in DOC_KEYS:
        series = numbering[key]
        writer.writerow(
            {
                "section": "numbering",
                "key": key,
                "prefix": _cell(series.get("prefix")),
                "include_year": _cell(series.get("include_year")),
                "pad": _cell(series.get("pad")),
                "next_number": _cell(series.get("next_number")),
                "preview": _cell(previews.get(key)),
                "value": "",
            }
        )
    for key in (
        "invoice_print_template",
        "receipt_print_template",
        "document_header",
        "document_footer",
    ):
        writer.writerow(
            {
                "section": "print_template",
                "key": key,
                "prefix": "",
                "include_year": "",
                "pad": "",
                "next_number": "",
                "preview": "",
                "value": _cell(print_tpl.get(key)),
            }
        )
    return buf.getvalue()
