"""CSV export for platform staff users & sessions (Stage 149)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app import platform as platform_svc
from app.platform_const import PLATFORM_ROLES, PLATFORM_TENANT_ID
from app.rbac import serialize_user
from app.session_passkey_doc_export import _cell

PLATFORM_USER_EXPORT_COLUMNS = [
    "id",
    "email",
    "full_name",
    "role",
    "is_active",
    "email_verified",
    "totp_enabled",
    "last_session_at",
    "active_session_count",
    "invite_sent",
    "invite_mode",
    "invite_created_at",
    "invite_error",
    "created_at",
]

PLATFORM_SESSION_EXPORT_COLUMNS = [
    "id",
    "user_id",
    "email",
    "full_name",
    "ip_address",
    "user_agent",
    "expires_at",
    "created_at",
    "current",
]


async def export_platform_users_csv(
    db: AsyncSession,
    *,
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> str:
    """Stage 149 U1 — platform staff roster CSV (no password/TOTP secrets)."""
    await platform_svc.ensure_platform_tenant(db)
    q_filter = (q or "").strip() or None
    role_filter = (role or "").strip() or None
    if role_filter and role_filter not in PLATFORM_ROLES:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {sorted(PLATFORM_ROLES)}",
        )
    filters = [m.User.tenant_id == PLATFORM_TENANT_ID]
    if q_filter:
        like = f"%{q_filter}%"
        filters.append(or_(m.User.email.ilike(like), m.User.full_name.ilike(like)))
    if role_filter:
        filters.append(m.User.role == role_filter)
    if is_active is not None:
        filters.append(m.User.is_active.is_(bool(is_active)))
    rows = (
        await db.execute(select(m.User).where(*filters).order_by(m.User.full_name.asc()))
    ).scalars().all()
    now = datetime.utcnow()
    last_by_user = {
        uid: created
        for uid, created in (
            await db.execute(
                select(m.AuthSession.user_id, func.max(m.AuthSession.created_at))
                .where(m.AuthSession.tenant_id == PLATFORM_TENANT_ID)
                .group_by(m.AuthSession.user_id)
            )
        ).all()
    }
    active_by_user = {
        uid: int(cnt or 0)
        for uid, cnt in (
            await db.execute(
                select(m.AuthSession.user_id, func.count())
                .where(
                    m.AuthSession.tenant_id == PLATFORM_TENANT_ID,
                    m.AuthSession.revoked_at.is_(None),
                    m.AuthSession.expires_at > now,
                )
                .group_by(m.AuthSession.user_id)
            )
        ).all()
    }
    invites = await platform_svc.latest_staff_invite_deliveries(db, [u.id for u in rows])

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PLATFORM_USER_EXPORT_COLUMNS)
    writer.writeheader()
    for u in rows:
        payload = serialize_user(u)
        last = last_by_user.get(u.id)
        invite = invites.get(u.id) or {}
        writer.writerow(
            {
                "id": _cell(payload.get("id")),
                "email": _cell(payload.get("email")),
                "full_name": _cell(payload.get("full_name")),
                "role": _cell(payload.get("role")),
                "is_active": _cell(payload.get("is_active")),
                "email_verified": _cell(payload.get("email_verified")),
                "totp_enabled": _cell(payload.get("totp_enabled")),
                "last_session_at": _cell(last.isoformat() + "Z" if last else None),
                "active_session_count": _cell(active_by_user.get(u.id, 0)),
                "invite_sent": _cell(invite.get("sent")),
                "invite_mode": _cell(invite.get("mode")),
                "invite_created_at": _cell(invite.get("created_at")),
                "invite_error": _cell(invite.get("error")),
                "created_at": _cell(payload.get("created_at")),
            }
        )
    return buf.getvalue()


async def export_platform_sessions_csv(
    db: AsyncSession,
    *,
    current_jti: str | None = None,
) -> str:
    """Stage 149 S1 — active platform staff sessions CSV (no refresh-token secrets / no jti)."""
    await platform_svc.ensure_platform_tenant(db)
    rows = (
        await db.execute(
            select(m.AuthSession, m.User)
            .join(m.User, m.User.id == m.AuthSession.user_id)
            .where(
                m.AuthSession.tenant_id == PLATFORM_TENANT_ID,
                m.AuthSession.revoked_at.is_(None),
            )
            .order_by(m.AuthSession.created_at.desc())
            .limit(200)
        )
    ).all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=PLATFORM_SESSION_EXPORT_COLUMNS)
    writer.writeheader()
    for s, u in rows:
        writer.writerow(
            {
                "id": _cell(s.id),
                "user_id": _cell(s.user_id),
                "email": _cell(u.email),
                "full_name": _cell(u.full_name),
                "ip_address": _cell(s.ip_address),
                "user_agent": _cell(s.user_agent),
                "expires_at": _cell(s.expires_at),
                "created_at": _cell(s.created_at),
                "current": _cell(s.jti == current_jti),
            }
        )
    return buf.getvalue()
