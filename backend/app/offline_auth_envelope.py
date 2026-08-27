"""7-day offline authorization envelope (§13–14).

Issues and validates a non-secret permissions snapshot for offline POS.
Does not claim Offline Complete. Never stores passwords or refresh tokens.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.rbac import permissions_for_role

OFFLINE_VALIDITY_DAYS = 7

# Relevant POS / offline modules snapshotted into the envelope (no secrets).
OFFLINE_PERMISSION_MODULES = (
    "pos",
    "credit",
    "inventory",
    "sales",
    "stores",
    "products",
)


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat() + "Z"


def _parse_iso(raw: Any) -> datetime | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.replace(tzinfo=None) if raw.tzinfo else raw
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1]
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def snapshot_permissions(
    role: str | None,
    permissions: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Filter to offline-relevant modules; never include tokens/secrets."""
    base = permissions if isinstance(permissions, dict) else permissions_for_role(role or "cashier")
    out: dict[str, list[str]] = {}
    if base.get("*") == ["*"] or (isinstance(base.get("*"), list) and "*" in (base.get("*") or [])):
        for mod in OFFLINE_PERMISSION_MODULES:
            out[mod] = ["read", "write", "approve"]
        return out
    for mod in OFFLINE_PERMISSION_MODULES:
        actions = base.get(mod)
        if isinstance(actions, list) and actions:
            out[mod] = [str(a) for a in actions]
    return out


def build_envelope_dict(
    *,
    tenant_id: str,
    company_id: str | None,
    store_id: str | None,
    user_id: str | None,
    device_id: str,
    permissions: dict[str, list[str]],
    issued_at: datetime,
    last_online_at: datetime,
    offline_valid_until: datetime,
    catalog_version: str | None = None,
    app_version: str | None = None,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "company_id": company_id,
        "store_id": store_id,
        "user_id": user_id,
        "device_id": device_id,
        "permissions": permissions,
        "issued_at": _iso(issued_at),
        "last_online_at": _iso(last_online_at),
        "offline_valid_until": _iso(offline_valid_until),
        "catalog_version": catalog_version,
        "app_version": app_version,
        "validity_days": OFFLINE_VALIDITY_DAYS,
    }


def envelope_from_device(row: m.OfflineDevice) -> dict[str, Any] | None:
    if row.offline_authorized_until is None and row.envelope_issued_at is None:
        return None
    perms = row.permissions_snapshot if isinstance(row.permissions_snapshot, dict) else {}
    issued = row.envelope_issued_at or row.last_online_at or row.created_at
    last_online = row.last_online_at or issued
    until = row.offline_authorized_until or (
        (last_online + timedelta(days=OFFLINE_VALIDITY_DAYS)) if last_online else None
    )
    if until is None:
        return None
    return build_envelope_dict(
        tenant_id=row.tenant_id,
        company_id=getattr(row, "company_id", None),
        store_id=getattr(row, "bound_store_id", None),
        user_id=getattr(row, "bound_user_id", None) or row.registered_by,
        device_id=row.id,
        permissions={k: list(v) for k, v in perms.items()} if perms else {},
        issued_at=issued,
        last_online_at=last_online,
        offline_valid_until=until,
        catalog_version=getattr(row, "catalog_version", None),
        app_version=getattr(row, "app_version", None),
    )


def apply_envelope_to_device(
    row: m.OfflineDevice,
    *,
    tenant_id: str,
    company_id: str | None,
    store_id: str | None,
    user_id: str | None,
    permissions: dict[str, list[str]],
    catalog_version: str | None = None,
    app_version: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write a fresh 7-day envelope onto the OfflineDevice row."""
    ts = now or datetime.utcnow()
    until = ts + timedelta(days=OFFLINE_VALIDITY_DAYS)
    row.company_id = company_id
    row.bound_user_id = user_id
    row.bound_store_id = store_id
    row.permissions_snapshot = permissions
    row.envelope_issued_at = ts
    row.last_online_at = ts
    row.offline_authorized_until = until
    if catalog_version is not None:
        row.catalog_version = (catalog_version or "").strip() or None
    if app_version is not None:
        row.app_version = (app_version or "").strip() or None
    row.last_seen_at = ts
    row.updated_at = ts
    if row.tenant_id != tenant_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "OFFLINE_ENVELOPE_TENANT_MISMATCH",
                "message": "Offline envelope tenant does not match device tenant",
                "device_id": row.id,
            },
        )
    return build_envelope_dict(
        tenant_id=row.tenant_id,
        company_id=row.company_id,
        store_id=row.bound_store_id,
        user_id=row.bound_user_id,
        device_id=row.id,
        permissions=permissions,
        issued_at=ts,
        last_online_at=ts,
        offline_valid_until=until,
        catalog_version=row.catalog_version,
        app_version=row.app_version,
    )


async def issue_envelope(
    db: AsyncSession,
    row: m.OfflineDevice,
    *,
    claims: dict,
    store_id: str | None = None,
    catalog_version: str | None = None,
    app_version: str | None = None,
    permissions: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Online bind/refresh — always issues a new 7-day window (JWT already verified)."""
    role = (claims.get("role") or "cashier").strip().lower()
    overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
    snap = permissions if permissions is not None else snapshot_permissions(role, overrides)
    envelope = apply_envelope_to_device(
        row,
        tenant_id=claims["tenant_id"],
        company_id=claims.get("company_id"),
        store_id=(store_id or "").strip() or None,
        user_id=claims.get("sub"),
        permissions=snap,
        catalog_version=catalog_version,
        app_version=app_version,
    )
    await db.flush()
    return envelope


def _mismatch(code: str, message: str, *, device_id: str, **extra: Any) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": code,
            "message": message,
            "device_id": device_id,
            **extra,
        },
    )


def validate_client_envelope(
    row: m.OfflineDevice,
    client_envelope: dict | None,
    *,
    tenant_id: str,
    now: datetime | None = None,
) -> None:
    """Reject expired or mismatched client/server envelope on sync."""
    ts = now or datetime.utcnow()

    server_until = row.offline_authorized_until
    # Inclusive expiry matches client isEnvelopeExpired (until <= now).
    if server_until is not None and server_until <= ts:
        raise _mismatch(
            "OFFLINE_ENVELOPE_EXPIRED",
            "Offline authorization envelope expired — reconnect online to renew",
            device_id=row.id,
            offline_valid_until=_iso(server_until),
        )

    if not client_envelope:
        return

    if not isinstance(client_envelope, dict):
        raise HTTPException(status_code=400, detail="auth_envelope must be an object")

    env_device = str(client_envelope.get("device_id") or "").strip()
    if env_device and env_device != row.id:
        raise _mismatch(
            "OFFLINE_ENVELOPE_DEVICE_MISMATCH",
            "Offline envelope device_id does not match sync device",
            device_id=row.id,
            envelope_device_id=env_device,
        )

    env_tenant = str(client_envelope.get("tenant_id") or "").strip()
    if env_tenant and (env_tenant != tenant_id or env_tenant != row.tenant_id):
        raise _mismatch(
            "OFFLINE_ENVELOPE_TENANT_MISMATCH",
            "Offline envelope tenant_id does not match session tenant",
            device_id=row.id,
            envelope_tenant_id=env_tenant,
        )

    env_company = client_envelope.get("company_id")
    if env_company is not None and str(env_company).strip() != "":
        bound = getattr(row, "company_id", None)
        if bound and str(env_company).strip() != bound:
            raise _mismatch(
                "OFFLINE_ENVELOPE_COMPANY_MISMATCH",
                "Offline envelope company_id does not match device binding",
                device_id=row.id,
                envelope_company_id=str(env_company).strip(),
                device_company_id=bound,
            )

    client_until = _parse_iso(client_envelope.get("offline_valid_until"))
    if client_until is not None and client_until <= ts:
        raise _mismatch(
            "OFFLINE_ENVELOPE_EXPIRED",
            "Client offline authorization envelope expired — reconnect online to renew",
            device_id=row.id,
            offline_valid_until=_iso(client_until),
        )
