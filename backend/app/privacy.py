"""Privacy: marketing email unsubscribe and data deletion requests.

Unsubscribe
    Ribdigi House marketing email carries a signed link per address. The link needs
    no sign-in and works once or many times; it only ever turns marketing mail off
    (or back on) for the address it was made for. Service notices about an account
    are not held back. The list lives in the main database, for the whole platform.

Deletion requests
    A signed-in person asks for their own account to be deleted, or a company admin
    asks for the whole company. The request needs the person's password. Ribdigi
    House reviews it: an approved personal request removes the sign-in and personal
    details at once (business records the company must keep stay, without the name);
    an approved company request is finished with the owner console's Delete company
    tool after the company has had the chance to download its data. Every step is
    written to the company's audit log and to the platform's, so the outcome is kept
    even after a company and its rows are gone.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.config import settings
from app.honesty import optional_honest_narrative

SCOPE_MARKETING = "marketing"
DELETION_SCOPES = ("my_account", "company")
OPEN_STATUSES = ("pending", "approved")


# ---- Unsubscribe links ----------------------------------------------------------------


def _key() -> bytes:
    return hashlib.sha256(f"email-unsubscribe:{settings.JWT_SECRET_KEY}".encode()).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    text = (text or "").strip()
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def normalize_email(email: str | None) -> str:
    return (email or "").strip().lower()


def unsubscribe_token(email: str) -> str:
    sig = hmac.new(_key(), normalize_email(email).encode(), hashlib.sha256).digest()
    return _b64(sig)[:32]


def encoded_email(email: str) -> str:
    return _b64(normalize_email(email).encode())


def verify_link(e: str, t: str) -> str | None:
    """The address a link was made for, or None when the link was changed or is not ours."""
    try:
        email = normalize_email(_unb64(e).decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not email or "@" not in email or len(email) > 255:
        return None
    if not hmac.compare_digest(unsubscribe_token(email), (t or "").strip()):
        return None
    return email


def unsubscribe_page_url(email: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/unsubscribe?e={quote(encoded_email(email))}&t={quote(unsubscribe_token(email))}"


def one_click_url(email: str) -> str:
    """RFC 8058 one-click target. /api/v1 on the site address reaches the API."""
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/api/v1/email/unsubscribe?e={quote(encoded_email(email))}&t={quote(unsubscribe_token(email))}"


def list_unsubscribe_headers(email: str) -> dict[str, str]:
    return {
        "List-Unsubscribe": f"<{one_click_url(email)}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    shown = local[:2] if len(local) > 2 else local[:1]
    return f"{shown}{'*' * max(1, len(local) - len(shown))}@{domain}"


async def is_suppressed(db: AsyncSession, email: str) -> bool:
    row = (
        await db.execute(
            select(m.EmailSuppression.id).where(
                m.EmailSuppression.email == normalize_email(email),
                m.EmailSuppression.scope == SCOPE_MARKETING,
            )
        )
    ).first()
    return row is not None


async def suppressed_among(db: AsyncSession, emails: list[str]) -> set[str]:
    wanted = {normalize_email(e) for e in emails if e}
    if not wanted:
        return set()
    out: set[str] = set()
    items = sorted(wanted)
    for i in range(0, len(items), 500):
        chunk = items[i : i + 500]
        rows = await db.execute(
            select(m.EmailSuppression.email).where(
                m.EmailSuppression.email.in_(chunk),
                m.EmailSuppression.scope == SCOPE_MARKETING,
            )
        )
        out.update(r[0] for r in rows)
    return out


async def set_marketing(db: AsyncSession, email: str, *, subscribed: bool, source: str) -> bool:
    """Turn Ribdigi House marketing email on or off for one address. Returns the new state."""
    email = normalize_email(email)
    if not email:
        raise HTTPException(status_code=422, detail="No email address")
    if subscribed:
        await db.execute(
            delete(m.EmailSuppression).where(
                m.EmailSuppression.email == email, m.EmailSuppression.scope == SCOPE_MARKETING
            )
        )
    elif not await is_suppressed(db, email):
        db.add(m.EmailSuppression(email=email, scope=SCOPE_MARKETING, source=source[:30]))
    await db.commit()
    return subscribed


# ---- Deletion requests ----------------------------------------------------------------


def serialize_request(row: m.DataDeletionRequest) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "scope": row.scope,
        "requested_by": row.requested_by,
        "requester_email": row.requester_email,
        "requester_name": row.requester_name,
        "reason": row.reason,
        "status": row.status,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "decision_note": row.decision_note,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _audit(db, *, tenant_id: str, user_id: str | None, action: str, row: m.DataDeletionRequest, extra: dict | None = None) -> None:
    await audit_svc.record_event(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        module="security",
        action=action,
        entity="data_deletion_request",
        entity_id=row.id,
        details={"scope": row.scope, "status": row.status, "company_id": row.tenant_id, **(extra or {})},
    )


async def create_request(
    db: AsyncSession,
    *,
    claims: dict,
    scope: str,
    password: str,
    reason: str | None,
) -> m.DataDeletionRequest:
    from app.security import verify_password

    if scope not in DELETION_SCOPES:
        raise HTTPException(status_code=422, detail="Choose my_account or company")
    tenant_id = str(claims.get("tenant_id") or "")
    user_id = str(claims.get("login_user_id") or claims.get("sub") or "")
    user = await db.get(m.User, user_id)
    if not user or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Account not found")
    # Identity check: the signed-in person proves it again with their password.
    if not verify_password(password or "", user.password_hash or ""):
        raise HTTPException(status_code=401, detail="That password is not right")
    from app.rbac import is_platform_role

    if is_platform_role(user.role) or user.role == "super_admin":
        raise HTTPException(status_code=400, detail="Ribdigi House staff accounts are closed from the platform Staff page")
    if scope == "company" and user.role != "company_admin":
        raise HTTPException(status_code=403, detail="Only a company admin can ask for the whole company to be deleted")
    open_q = select(m.DataDeletionRequest.id).where(
        m.DataDeletionRequest.tenant_id == tenant_id,
        m.DataDeletionRequest.scope == scope,
        m.DataDeletionRequest.status.in_(OPEN_STATUSES),
    )
    if scope == "my_account":
        open_q = open_q.where(m.DataDeletionRequest.requested_by == user.id)
    if (await db.execute(open_q)).first():
        raise HTTPException(status_code=409, detail="A request like this is already open")
    row = m.DataDeletionRequest(
        tenant_id=tenant_id,
        scope=scope,
        requested_by=user.id,
        requester_email=user.email,
        requester_name=user.full_name,
        reason=optional_honest_narrative(reason, label="Reason", max_length=1000),
        status="pending",
    )
    db.add(row)
    await db.flush()
    await _audit(db, tenant_id=tenant_id, user_id=user.id, action="data_deletion_requested", row=row)
    await db.commit()
    await db.refresh(row)
    return row


async def list_for_company(db: AsyncSession, *, claims: dict) -> list[dict]:
    tenant_id = str(claims.get("tenant_id") or "")
    user_id = str(claims.get("login_user_id") or claims.get("sub") or "")
    q = select(m.DataDeletionRequest).where(m.DataDeletionRequest.tenant_id == tenant_id)
    if (claims.get("role") or "") != "company_admin":
        q = q.where(m.DataDeletionRequest.requested_by == user_id)
    rows = (await db.execute(q.order_by(m.DataDeletionRequest.created_at.desc()).limit(50))).scalars().all()
    return [serialize_request(r) for r in rows]


async def cancel_request(db: AsyncSession, *, claims: dict, request_id: str) -> m.DataDeletionRequest:
    tenant_id = str(claims.get("tenant_id") or "")
    user_id = str(claims.get("login_user_id") or claims.get("sub") or "")
    row = await db.get(m.DataDeletionRequest, request_id)
    if not row or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.requested_by != user_id and (claims.get("role") or "") != "company_admin":
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="Only a request still waiting for review can be cancelled")
    row.status = "cancelled"
    row.decided_at = datetime.utcnow()
    row.decided_by = user_id
    await _audit(db, tenant_id=tenant_id, user_id=user_id, action="data_deletion_cancelled", row=row)
    await db.commit()
    return row


async def decide(
    db: AsyncSession,
    *,
    row: m.DataDeletionRequest,
    decision: str,
    note: str | None,
    actor_id: str,
    actor_tenant_id: str,
    platform_db: AsyncSession | None = None,
) -> m.DataDeletionRequest:
    """Ribdigi House's decision. `db` is the session holding the request (the company's desk)."""
    from app.user_accounts import delete_tenant_user

    note_clean = optional_honest_narrative(note, label="Note", max_length=1000)
    now = datetime.utcnow()
    if decision == "reject":
        if row.status != "pending":
            raise HTTPException(status_code=409, detail="Only a pending request can be rejected")
        if not note_clean:
            raise HTTPException(status_code=422, detail="Say why the request is refused, so the person can be told")
        row.status = "rejected"
    elif decision == "approve":
        if row.status != "pending":
            raise HTTPException(status_code=409, detail="Only a pending request can be approved")
        if row.scope == "my_account":
            # Removes the sign-in, sessions, passkeys, 2FA and links to stores and staff roles.
            # Business records stay with the company but no longer point at this person.
            await delete_tenant_user(db, tenant_id=row.tenant_id, actor_id=actor_id, user_id=row.requested_by)
            row.status = "completed"
            row.completed_at = now
        else:
            row.status = "approved"
    elif decision == "complete":
        if row.status != "approved":
            raise HTTPException(status_code=409, detail="Approve the request first")
        row.status = "completed"
        row.completed_at = now
    else:
        raise HTTPException(status_code=422, detail="Decision must be approve, reject or complete")
    row.decided_by = actor_id
    row.decided_at = now
    row.decision_note = note_clean
    action = f"data_deletion_{row.status}"
    await _audit(db, tenant_id=row.tenant_id, user_id=None, action=action, row=row, extra={"decided_by": actor_id})
    if platform_db is not None and platform_db is not db:
        await _audit(platform_db, tenant_id=actor_tenant_id, user_id=actor_id, action=action, row=row)
        await platform_db.commit()
    elif actor_tenant_id != row.tenant_id:
        await _audit(db, tenant_id=actor_tenant_id, user_id=actor_id, action=action, row=row)
    await db.commit()
    return row
