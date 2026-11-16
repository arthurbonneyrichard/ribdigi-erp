"""Sign-in protection shared by every authentication route.

Two independent guards:

* **Per-IP buckets** (Redis sliding window via ``app.rate_limit``): each kind of auth request has its
  own bucket keyed only by the client IP (IPv6 grouped per /64). Neither the username nor the
  ``X-Tenant-ID`` header is part of the key, so rotating them does not open a new bucket, and a
  successful sign-in does not empty the bucket. Sign-in has two: every request (30 a minute, so a
  shop where everyone shares one IP can still sign in at shift change) and failed tries only (5 a
  minute, checked before the password so guessing stops there).
* **Account lockout** (Postgres, on the ``users`` row): after ``AUTH_LOCKOUT_THRESHOLD`` wrong tries
  in a row the account is locked for the next step of ``AUTH_LOCKOUT_MINUTES`` (15, 30, 60, 120 by
  default; the last step repeats, never permanent). It is counted per account, so it holds whatever
  IP the attacker uses, across workers and while Redis is down. Counters move with single
  conditional UPDATE statements so simultaneous wrong tries cannot skip the lock.

Unauthenticated callers always get the same answer for an unknown account, a wrong password and a
locked account (``GENERIC_LOGIN_FAILURE``); the lock is only visible to authorised administrators.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import math
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import models as m
from app.config import settings
from app.middleware import client_ip_from_request
from app.rate_limit import RateLimitBackendUnavailable, rate_limiter

logger = logging.getLogger(__name__)
security_log = logging.getLogger("ribdigi.security")

GENERIC_LOGIN_FAILURE = (
    "Invalid username or password. If you have made several unsuccessful attempts, please try again later."
)

# bucket -> (limit setting, window setting)
_BUCKETS: dict[str, tuple[str, str]] = {
    # Every sign-in request, and separately only the failed ones (unknown company or account, wrong
    # password or code, locked account). The failed bucket is checked before any password check.
    "login": ("AUTH_IP_LOGIN_REQUEST_LIMIT", "AUTH_IP_LOGIN_WINDOW_SECONDS"),
    "login_fail": ("AUTH_IP_LOGIN_LIMIT", "AUTH_IP_LOGIN_WINDOW_SECONDS"),
    "shop_login": ("AUTH_IP_LOGIN_REQUEST_LIMIT", "AUTH_IP_LOGIN_WINDOW_SECONDS"),
    "shop_login_fail": ("AUTH_IP_LOGIN_LIMIT", "AUTH_IP_LOGIN_WINDOW_SECONDS"),
    "password_reset": ("AUTH_IP_RESET_LIMIT", "AUTH_IP_RESET_WINDOW_SECONDS"),
    "otp_request": ("AUTH_IP_OTP_REQUEST_LIMIT", "AUTH_IP_OTP_REQUEST_WINDOW_SECONDS"),
    "otp_verify": ("AUTH_IP_OTP_VERIFY_LIMIT", "AUTH_IP_OTP_VERIFY_WINDOW_SECONDS"),
    "register": ("AUTH_IP_REGISTER_LIMIT", "AUTH_IP_REGISTER_WINDOW_SECONDS"),
}

# Process counters for /api/v1/metrics (per worker, like the HTTP counters).
_counter_lock = threading.Lock()
_counters: dict[tuple[str, str], int] = {}


def _bump(event: str, label: str) -> None:
    with _counter_lock:
        _counters[(event, label)] = _counters.get((event, label), 0) + 1


def counters_snapshot() -> dict[tuple[str, str], int]:
    with _counter_lock:
        return dict(_counters)


def reset_counters_for_tests() -> None:
    with _counter_lock:
        _counters.clear()


# The failed-try bucket checked alongside each sign-in request bucket.
_FAIL_BUCKET = {"login": "login_fail", "shop_login": "shop_login_fail"}


def utcnow() -> datetime:
    """Timezone-aware UTC (the lockout columns are ``UTCDateTime``)."""
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """Aware UTC from either kind; a naive value is read as UTC (how this schema stores time)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    value = as_utc(value)
    if value is None:
        return None
    return value.replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def bucket_limit(bucket: str) -> tuple[int, int]:
    limit_name, window_name = _BUCKETS[bucket]
    return max(int(getattr(settings, limit_name)), 1), max(int(getattr(settings, window_name)), 1)


def ip_bucket_key(ip: str) -> str:
    """IPv4 as is; IPv6 per /64 (one customer line), so a host cannot rotate addresses in its range."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return (ip or "unknown").strip()[:64] or "unknown"
    if addr.version == 6:
        if addr.ipv4_mapped:
            return str(addr.ipv4_mapped)
        return str(ipaddress.ip_network(f"{addr}/64", strict=False))
    return str(addr)


def security_event(event: str, *, request: Request | None = None, **fields: Any) -> None:
    """One JSON line on the ``ribdigi.security`` logger. Never pass passwords, codes or tokens."""
    payload: dict[str, Any] = {"event": event, "at": iso_utc(utcnow())}
    if request is not None:
        payload["ip"] = client_ip_from_request(request)
        payload["user_agent"] = (request.headers.get("user-agent") or "")[:255]
        payload["path"] = request.url.path
        rid = getattr(request.state, "request_id", None)
        if rid:
            payload["request_id"] = rid
    payload.update({k: v for k, v in fields.items() if v is not None})
    security_log.warning(json.dumps(payload, default=str, sort_keys=True))


# ---------------------------------------------------------------------------
# Per-IP buckets
# ---------------------------------------------------------------------------


def _ip_key(request: Request, bucket: str) -> str:
    return f"auth:{bucket}:{ip_bucket_key(client_ip_from_request(request))}"


def _backend_down(request: Request, bucket: str) -> HTTPException:
    _bump("auth_rate_limit_backend_down", bucket)
    security_event("auth_rate_limit_backend_down", request=request, bucket=bucket)
    return HTTPException(
        status_code=503,
        detail={
            "code": "AUTH_TEMPORARILY_UNAVAILABLE",
            "message": "Sign-in is briefly unavailable. Try again in a minute.",
        },
        headers={"Retry-After": "30"},
    )


async def check_ip(request: Request, bucket: str) -> None:
    """Count this request against the caller's IP bucket; 429 with Retry-After when over.

    Sign-in buckets also refuse, before any password check, while this IP's failed-try bucket is full.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
    limit, window = bucket_limit(bucket)
    fail_closed = settings.AUTH_RATE_LIMIT_FAIL_CLOSED
    try:
        allowed, retry_after, _remaining = await rate_limiter.allow(
            _ip_key(request, bucket), limit, window, fail_closed=fail_closed
        )
        if allowed and bucket in _FAIL_BUCKET:
            fail_bucket = _FAIL_BUCKET[bucket]
            fail_limit, fail_window = bucket_limit(fail_bucket)
            full, fail_retry = await rate_limiter.peek(
                _ip_key(request, fail_bucket), fail_limit, fail_window, fail_closed=fail_closed
            )
            if full:
                allowed, retry_after = False, fail_retry
                bucket, limit, window = fail_bucket, fail_limit, fail_window
    except RateLimitBackendUnavailable:
        raise _backend_down(request, bucket) from None
    if rate_limiter.degraded:
        # Still limited, but per worker until Redis answers again.
        _bump("auth_rate_limit_degraded", bucket)
    if allowed:
        return
    retry_after = max(int(retry_after or 1), 1)
    _bump("auth_rate_limited", bucket)
    security_event(
        "auth_rate_limited", request=request, bucket=bucket, limit=limit, window_seconds=window,
        retry_after=retry_after,
    )
    minutes = max(1, math.ceil(retry_after / 60))
    wait = f"{minutes} minute" + ("" if minutes == 1 else "s")
    raise HTTPException(
        status_code=429,
        detail={
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many attempts from this network. Try again in {wait}.",
            "retry_after": retry_after,
        },
        headers={
            "Retry-After": str(retry_after),
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": "0",
        },
    )


async def record_ip_failure(request: Request | None, bucket: str = "login_fail") -> None:
    """Add one failed try to the caller's IP. Never raises: the caller is already answering."""
    if request is None or not settings.RATE_LIMIT_ENABLED:
        return
    limit, window = bucket_limit(bucket)
    try:
        await rate_limiter.allow(_ip_key(request, bucket), limit, window)
    except Exception:
        logger.exception("auth ip failure count skipped")


def ip_limit(bucket: str):
    """FastAPI dependency: ``Depends(auth_guard.ip_limit("login"))``."""
    if bucket not in _BUCKETS:
        raise ValueError(f"unknown auth bucket {bucket}")

    async def _dependency(request: Request) -> None:
        await check_ip(request, bucket)

    _dependency.__name__ = f"auth_ip_limit_{bucket}"
    return _dependency


# ---------------------------------------------------------------------------
# Account lockout
# ---------------------------------------------------------------------------

_DUMMY_HASH: str | None = None


async def burn_password_check(password: str) -> None:
    """Spend the same bcrypt time as a real check, so an unknown or locked account answers no faster."""
    global _DUMMY_HASH
    from app.security import hash_password, verify_password

    if _DUMMY_HASH is None:
        _DUMMY_HASH = await asyncio.to_thread(hash_password, "ribdigi-timing-equaliser-not-a-password")
    try:
        await asyncio.to_thread(verify_password, password or "x", _DUMMY_HASH)
    except Exception:  # pragma: no cover - timing only
        pass


def is_locked(user: Any | None, now: datetime | None = None) -> bool:
    """For a staff ``User`` or a storefront ``EcommerceShopper`` (same lockout columns)."""
    if user is None or user.locked_until is None:
        return False
    return as_utc(user.locked_until) > (now or utcnow())


def lockout_minutes_for_step(step: int) -> int:
    """Step 0 = first lockout. The last configured value repeats."""
    ladder = settings.auth_lockout_minutes
    return ladder[min(max(step, 0), len(ladder) - 1)]


def lock_state(user: Any, now: datetime | None = None) -> dict:
    """What an authorised administrator sees about one account's sign-in protection."""
    now = now or utcnow()
    locked = is_locked(user, now)
    return {
        "locked": locked,
        "locked_until": iso_utc(user.locked_until) if locked else None,
        "locked_at": iso_utc(user.locked_at) if locked else None,
        "seconds_remaining": int((as_utc(user.locked_until) - now).total_seconds()) if locked else 0,
        "failed_login_attempts": int(user.failed_login_attempts or 0),
        "lockout_threshold": int(settings.AUTH_LOCKOUT_THRESHOLD),
        "last_failed_login_at": iso_utc(user.last_failed_login_at),
        "lockout_count": int(user.lockout_count or 0),
        "next_lockout_minutes": lockout_minutes_for_step(_effective_step(user, now)),
    }


def _effective_step(user: Any, now: datetime) -> int:
    """Ladder step for the next lockout; a quiet spell longer than the reset window starts over."""
    count = int(user.lockout_count or 0)
    if count and user.locked_at is not None:
        if now - as_utc(user.locked_at) > timedelta(hours=max(int(settings.AUTH_LOCKOUT_LADDER_RESET_HOURS), 1)):
            return 0
    return count


async def _audit(db: AsyncSession, *, entity: str = "user", **kwargs) -> None:
    from app import audit as audit_svc

    try:
        async with db.begin_nested():
            await audit_svc.record_event(db, module="auth", entity=entity, **kwargs)
    except Exception:
        logger.exception("auth audit %s skipped", kwargs.get("action"))


def _request_fields(request: Request | None) -> dict:
    if request is None:
        return {}
    return {
        "ip_address": client_ip_from_request(request),
        "user_agent": (request.headers.get("user-agent") or "")[:255] or None,
    }


def _subject(account: Any) -> tuple[Any, str, str | None]:
    """(model, audit entity, audit user_id) for a staff user or a storefront shopper."""
    if isinstance(account, m.EcommerceShopper):
        return m.EcommerceShopper, "shopper", None
    return m.User, "user", account.id


async def _count_failure(db: AsyncSession, model: Any, account_id: str, now: datetime) -> tuple[bool, int | None, int | None]:
    """Atomic +1 and, on the threshold, the lock. Returns (locked_now, attempts, minutes)."""
    threshold = max(int(settings.AUTH_LOCKOUT_THRESHOLD), 1)
    # A locked account is not counted (its tries are refused before any password check).
    row = (
        await db.execute(
            update(model)
            .where(model.id == account_id)
            .where((model.locked_until.is_(None)) | (model.locked_until <= now))
            .values(failed_login_attempts=model.failed_login_attempts + 1, last_failed_login_at=now)
            .returning(model.failed_login_attempts, model.lockout_count, model.locked_at)
            .execution_options(synchronize_session=False)
        )
    ).first()
    if row is None:
        return False, None, None
    attempts, prior_count, prior_locked_at = int(row[0] or 0), int(row[1] or 0), row[2]
    if attempts < threshold:
        return False, attempts, None
    step = _effective_step(SimpleNamespace(lockout_count=prior_count, locked_at=prior_locked_at), now)
    minutes = lockout_minutes_for_step(step)
    # Only the request that still sees the count over the threshold takes the lock; a
    # simultaneous one finds the count already reset and does nothing.
    won = (
        await db.execute(
            update(model)
            .where(model.id == account_id, model.failed_login_attempts >= threshold)
            .values(
                failed_login_attempts=0,
                locked_at=now,
                locked_until=now + timedelta(minutes=minutes),
                lockout_count=step + 1,
            )
            .returning(model.id)
            .execution_options(synchronize_session=False)
        )
    ).first()
    return won is not None, attempts, minutes


async def register_failure(
    db: AsyncSession,
    user: Any,
    *,
    request: Request | None,
    reason: str = "password",
    action: str = "login_failed",
    ip_bucket: str = "login_fail",
) -> bool:
    """Count one wrong try for this account (and its IP), lock it on the threshold, audit, commit.

    ``user`` is a staff ``User`` or a storefront ``EcommerceShopper``. Returns True when this try
    locked the account. Never raises for database trouble: the caller still answers generically.
    """
    now = utcnow()
    model, entity, actor = _subject(user)
    account_id, tenant_id = user.id, user.tenant_id
    threshold = max(int(settings.AUTH_LOCKOUT_THRESHOLD), 1)
    locked_now, attempts, minutes = False, None, None
    await record_ip_failure(request, ip_bucket)
    try:
        locked_now, attempts, minutes = await _count_failure(db, model, account_id, now)
        await _audit(
            db,
            entity=entity,
            tenant_id=tenant_id,
            user_id=actor,
            action=action,
            entity_id=account_id,
            details={"reason": reason, "attempts": attempts, "threshold": threshold},
            **_request_fields(request),
        )
        if locked_now:
            await _audit(
                db,
                entity=entity,
                tenant_id=tenant_id,
                user_id=actor,
                action="account_locked",
                entity_id=account_id,
                details={
                    "minutes": minutes,
                    "locked_until": iso_utc(now + timedelta(minutes=minutes or 0)),
                    "trigger": reason,
                },
                **_request_fields(request),
            )
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("auth failed-attempt update skipped")
    _bump("auth_login_failed", reason)
    security_event(
        "auth_login_failed", request=request, tenant_id=tenant_id, account=entity, account_id=account_id,
        reason=reason, attempts=attempts,
    )
    if locked_now:
        _bump("auth_account_locked", reason)
        security_event(
            "auth_account_locked", request=request, tenant_id=tenant_id, account=entity,
            account_id=account_id, minutes=minutes,
        )
    return locked_now


async def register_unknown(request: Request | None, *, reason: str, tenant_id: str | None = None,
                           ip_bucket: str = "login_fail") -> None:
    """A try on an account or company that does not exist: counted on the IP only."""
    await record_ip_failure(request, ip_bucket)
    _bump("auth_login_failed", reason)
    security_event("auth_login_failed", request=request, tenant_id=tenant_id, reason=reason)


async def register_blocked_locked(
    db: AsyncSession, user: Any, *, request: Request | None, ip_bucket: str = "login_fail"
) -> None:
    """A try on an account that is locked: counted on the IP, audited, answered like a wrong password."""
    _model, entity, actor = _subject(user)
    await record_ip_failure(request, ip_bucket)
    _bump("auth_login_blocked_locked", "locked")
    security_event(
        "auth_login_blocked_locked", request=request, tenant_id=user.tenant_id, account=entity,
        account_id=user.id, locked_until=iso_utc(user.locked_until),
    )
    try:
        await _audit(
            db,
            entity=entity,
            tenant_id=user.tenant_id,
            user_id=actor,
            action="login_blocked_locked",
            entity_id=user.id,
            details={"locked_until": iso_utc(user.locked_until)},
            **_request_fields(request),
        )
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        logger.exception("auth locked-attempt audit skipped")


def register_success(user: Any) -> None:
    """A good sign-in clears the account's counters (the caller commits). IP buckets are untouched."""
    user.failed_login_attempts = 0
    user.lockout_count = 0
    user.locked_until = None
    user.locked_at = None


def clear_after_password_reset(user: Any) -> None:
    """A verified password reset proves the owner: lift any lock and start the ladder over."""
    register_success(user)


def reject_generic() -> HTTPException:
    return HTTPException(status_code=401, detail=GENERIC_LOGIN_FAILURE)


async def unlock_account(
    db: AsyncSession,
    user: Any,
    *,
    actor_id: str,
    actor_tenant_id: str,
    request: Request | None,
    note: str | None = None,
) -> dict:
    """Administrator unlock. The caller has already checked permission and tenant scope."""
    _model, entity, _actor = _subject(user)
    was = lock_state(user)
    register_success(user)
    details = {
        "target_user_id": user.id,
        "target_tenant_id": user.tenant_id,
        "was_locked": was["locked"],
        "locked_until": was["locked_until"],
        "failed_login_attempts": was["failed_login_attempts"],
    }
    if note:
        details["note"] = note[:200]
    # Into the account's own company log, and the actor's when they are platform staff elsewhere.
    await _audit(
        db, entity=entity, tenant_id=user.tenant_id, user_id=actor_id, action="account_unlocked", entity_id=user.id,
        details=details, **_request_fields(request),
    )
    if actor_tenant_id != user.tenant_id:
        await _audit(
            db, entity=entity, tenant_id=actor_tenant_id, user_id=actor_id, action="account_unlocked",
            entity_id=user.id,
            details=details, **_request_fields(request),
        )
    await db.commit()
    _bump("auth_account_unlocked", "admin")
    security_event(
        "auth_account_unlocked", request=request, tenant_id=user.tenant_id, user_id=user.id, actor_id=actor_id,
    )
    return lock_state(user)


AUTH_EVENT_ACTIONS = (
    "login",
    "login_failed",
    "2fa_failed",
    "2fa_challenge",
    "account_locked",
    "account_unlocked",
    "login_blocked_locked",
    "login_blocked_unverified",
    "password_reset_requested",
    "password_reset_completed",
    "full_sign_in_failed",
    "logout",
)


async def recent_auth_events(
    db: AsyncSession, *, tenant_id: str, user_id: str | None = None, limit: int = 50
) -> list[dict]:
    """Latest sign-in security events for one company (and optionally one account)."""
    stmt = select(m.AuditLog).where(
        m.AuditLog.tenant_id == tenant_id,
        m.AuditLog.module == "auth",
        m.AuditLog.action.in_(AUTH_EVENT_ACTIONS),
    )
    if user_id:
        stmt = stmt.where((m.AuditLog.entity_id == user_id) | (m.AuditLog.user_id == user_id))
    rows = (
        await db.execute(stmt.order_by(m.AuditLog.created_at.desc()).limit(max(1, min(limit, 200))))
    ).scalars().all()
    out = []
    for row in rows:
        details = dict(row.details or {})
        details.pop("email", None)
        out.append(
            {
                "id": row.id,
                "action": row.action,
                "user_id": row.user_id,
                "entity_id": row.entity_id,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "details": details,
                "created_at": iso_utc(row.created_at),
            }
        )
    return out
