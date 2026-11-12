"""Till lock, cashier passcodes and who is really at the till.

A browser signs in once, but many cashiers can share that till. A cashier unlocks with
a personal passcode and gets a short signed operator token. The browser sends it as
``X-Pos-Operator`` alongside the normal session, and on till paths ``current_claims``
acts as that cashier, so shifts, sales, audit rows and permissions all belong to the
person at the till.

The operator identity is honoured on ``OPERATOR_PATHS`` only. A six-digit passcode must
never open the rest of the ERP, even when it belongs to a company admin.

A passcode is the only way through the lock. So the lock starts when a company has its
first active passcode. Before that nobody could unlock, so tills stay open and till writes
keep working on the signed-in account.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWTError
from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit as audit_svc
from app import models as m
from app.config import settings
from app.rbac import has_permission

SURFACE_MODULES = {"retail": "pos", "restaurant": "restaurant"}
OPERATOR_HEADER = "X-Pos-Operator"

PASSCODE_LENGTH = 6
# Screen locks after this much quiet. The server allows extra time for a slow network.
IDLE_LOCK_SECONDS = 60
SERVER_IDLE_LIMIT_SECONDS = 150
OPERATOR_TOKEN_HOURS = 16

DEVICE_FAIL_LIMIT = 5
DEVICE_LOCK_SECONDS = 300
ACCOUNT_FAIL_LIMIT = 15
ACCOUNT_LOCK_SECONDS = 900
FAIL_WINDOW_SECONDS = 900

API = "/api/v1"
LOCK_API_PREFIX = f"{API}/pos/lock/"
# The cashier at the till acts on these paths. Everything else stays on the signed-in account.
OPERATOR_PATHS = (
    f"{API}/pos/",
    f"{API}/printers/",
    f"{API}/customers",
    f"{API}/sales/quotations",
    f"{API}/pharmacy/prescriptions",
    f"{API}/restaurant/orders",
    f"{API}/restaurant/till/",
)
OPERATOR_EXACT_PATHS = (f"{API}/me",)

# Writes that need an unlocked till once the company uses passcodes. Closing a shift stays
# open: the sign-out screen closes it from outside the till, under the cashier's own login.
_LOCKED_WRITES = (
    re.compile(rf"^{API}/pos/sales(/[^/]+/returns)?$"),
    re.compile(rf"^{API}/pos/sessions/open$"),
    re.compile(rf"^{API}/pos/sessions/[^/]+/(movements|opening-cash|drawer/open)$"),
    re.compile(rf"^{API}/restaurant/orders/[^/]+/complete$"),
    re.compile(rf"^{API}/restaurant/till/shift/open$"),
    re.compile(rf"^{API}/restaurant/till/shift/[^/]+/cash$"),
)


def _now() -> datetime:
    return datetime.utcnow()


def _locked_error(message: str = "This till is locked. Enter your passcode to carry on.") -> HTTPException:
    return HTTPException(status_code=423, detail={"code": "POS_LOCKED", "message": message})


def path_accepts_operator(path: str) -> bool:
    return path in OPERATOR_EXACT_PATHS or any(path.startswith(prefix) for prefix in OPERATOR_PATHS)


# A session opened with a passcode reaches only the till and Sales until a full sign-in.
# Writes are allowed on these prefixes; everything below is read-only for the till screens.
_TILL_ONLY_WRITE_PREFIXES = (
    f"{API}/pos/",
    f"{API}/printers/",
    f"{API}/customers",
    f"{API}/sales/",
    f"{API}/gift-cards",
    f"{API}/pharmacy/prescriptions",
    f"{API}/restaurant/orders",
    f"{API}/restaurant/till/",
)
_TILL_ONLY_READ_PREFIXES = (
    f"{API}/products",
    f"{API}/catalog/units",
    f"{API}/stores",
    f"{API}/tax/rates",
    f"{API}/restaurant/tables",
    f"{API}/restaurant/modifiers",
    f"{API}/restaurant/recipes",
    f"{API}/restaurant/sold-out",
)
_TILL_ONLY_EXACT = (
    f"{API}/me",
    f"{API}/tenants/me",
    f"{API}/tenants/me/logo",
    f"{API}/auth/logout",
    f"{API}/auth/full-sign-in",
)


def till_only_path_allowed(method: str, path: str) -> bool:
    if path in _TILL_ONLY_EXACT:
        return path.startswith(f"{API}/auth/") or method.upper() in {"GET", "HEAD", "OPTIONS"}
    if any(path.startswith(prefix) for prefix in _TILL_ONLY_WRITE_PREFIXES):
        return True
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return any(path.startswith(prefix) for prefix in _TILL_ONLY_READ_PREFIXES)
    return False


def till_only_error() -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": "TILL_ONLY",
            "message": "This till was opened with a passcode. Sign in fully with your password to use the rest of the system.",
        },
    )


async def restrict_session_to_till(db: AsyncSession, claims: dict) -> None:
    """The browser session behind a passcode unlock is held to the till and Sales."""
    jti = claims.get("jti")
    if not jti:
        return
    await db.execute(
        update(m.AuthSession)
        .where(m.AuthSession.jti == jti, m.AuthSession.tenant_id == claims["tenant_id"])
        .values(till_only=True)
    )


async def full_sign_in(db: AsyncSession, *, claims: dict, password: str) -> dict:
    """Lift the till-only hold with the signed-in account's own password."""
    tenant_id = claims["tenant_id"]
    user_id = claims["sub"]
    jti = claims.get("jti")
    if not jti:
        return {"till_only": False}
    scope = f"full-sign-in:{jti[:16]}"
    await assert_not_throttled(db, tenant_id, scope, user_id)
    user = await db.get(m.User, user_id)
    from app.security import verify_password

    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        left = await _record_failure(db, tenant_id, scope, user_id)
        await audit_svc.record_event(
            db, tenant_id=tenant_id, user_id=user_id, module="auth", action="full_sign_in_failed",
            entity="user", entity_id=user_id, details={"tries_left": left},
        )
        await db.commit()
        if left <= 0:
            raise _throttled_error(DEVICE_LOCK_SECONDS)
        raise HTTPException(
            status_code=403,
            detail={"code": "PASSWORD_INVALID", "message": "That password is not right.", "tries_left": left},
        )
    await _clear_failures(db, tenant_id, scope, user_id)
    await db.execute(
        update(m.AuthSession)
        .where(m.AuthSession.jti == jti, m.AuthSession.tenant_id == tenant_id)
        .values(till_only=False)
    )
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=user_id, module="auth", action="full_sign_in",
        entity="user", entity_id=user_id, details={"from": "till"},
    )
    await db.commit()
    return {"till_only": False}


# ---------- kiosk mode ----------

KIOSK_CODE_LENGTH = 8
KIOSK_VERIFIER_ROUNDS = 200_000


def kiosk_code() -> str:
    return str(settings.POS_KIOSK_EXIT_CODE or "").strip()


def kiosk_offline_verifier() -> dict:
    """Lets a till check the close code while offline without shipping the code itself."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", kiosk_code().encode(), salt, KIOSK_VERIFIER_ROUNDS)
    return {"salt": salt.hex(), "hash": digest.hex(), "rounds": KIOSK_VERIFIER_ROUNDS, "length": len(kiosk_code())}


async def close_kiosk(db: AsyncSession, *, claims: dict, device_id: str, surface: str, code: str) -> dict:
    tenant_id = claims["tenant_id"]
    user_id = claims.get("login_user_id") or claims["sub"]
    scope = f"kiosk:{device_id}"
    await assert_not_throttled(db, tenant_id, scope, user_id)
    expected = kiosk_code()
    if not expected or not hmac.compare_digest(code.encode(), expected.encode()):
        left = await _record_failure(db, tenant_id, scope, user_id)
        await _audit(db, tenant_id, action="pos_kiosk_close_failed", user_id=user_id, device_id=device_id,
                     surface=surface, details={"tries_left": left})
        await db.commit()
        if left <= 0:
            raise _throttled_error(DEVICE_LOCK_SECONDS)
        raise HTTPException(
            status_code=403,
            detail={"code": "KIOSK_CODE_INVALID", "message": "That code is not right.", "tries_left": left},
        )
    await _clear_failures(db, tenant_id, scope, user_id)
    await _audit(db, tenant_id, action="pos_kiosk_closed", user_id=user_id, device_id=device_id, surface=surface)
    await db.commit()
    return {"closed": True}


def path_needs_unlocked_till(method: str, path: str) -> bool:
    if method.upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    return any(pattern.match(path) for pattern in _LOCKED_WRITES)


def _pepper() -> bytes:
    """Key for the passcode lookup. Rotating it means reissuing every passcode."""
    configured = (settings.POS_PASSCODE_PEPPER or "").strip()
    if configured:
        return configured.encode("utf-8")
    return hashlib.sha256(f"pos-passcode:{settings.JWT_SECRET_KEY}".encode("utf-8")).digest()


def lookup_hash(tenant_id: str, passcode: str) -> str:
    return hmac.new(_pepper(), f"{tenant_id}:{passcode}".encode("utf-8"), hashlib.sha256).hexdigest()


def is_weak_passcode(passcode: str) -> bool:
    digits = [int(ch) for ch in passcode]
    steps = {b - a for a, b in zip(digits, digits[1:])}
    return steps in ({0}, {1}, {-1})


def validate_passcode(passcode: str) -> str:
    value = (passcode or "").strip()
    if not re.fullmatch(rf"\d{{{PASSCODE_LENGTH}}}", value):
        raise HTTPException(status_code=422, detail=f"A passcode is exactly {PASSCODE_LENGTH} digits.")
    if is_weak_passcode(value):
        raise HTTPException(
            status_code=422,
            detail="That passcode is too easy to guess. Avoid repeated digits and runs like 123456.",
        )
    return value


def user_permissions(user: m.User) -> dict | None:
    return user.permissions if isinstance(user.permissions, dict) else None


def user_can_use_till(user: m.User, surface: str) -> bool:
    module = SURFACE_MODULES[surface]
    return has_permission(user.role, module, "write", overrides=user_permissions(user))


def user_can_use_any_till(user: m.User) -> bool:
    return any(user_can_use_till(user, surface) for surface in SURFACE_MODULES)


async def enforcement_on(db: AsyncSession, tenant_id: str) -> bool:
    found = (
        await db.execute(
            select(m.PosCashierPasscode.id)
            .where(m.PosCashierPasscode.tenant_id == tenant_id, m.PosCashierPasscode.is_active.is_(True))
            .limit(1)
        )
    ).first()
    return found is not None


# ---------- operator token ----------


def issue_operator_token(session: m.PosOperatorSession) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "type": "pos_operator",
            "sub": session.user_id,
            "tenant_id": session.tenant_id,
            "sid": session.id,
            "jti": secrets.token_hex(12),
            "iat": int(now.timestamp()),
            "exp": now + timedelta(hours=OPERATOR_TOKEN_HOURS),
        },
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


async def _live_row_for_token(db: AsyncSession, raw: str, tenant_id: str) -> m.PosOperatorSession | None:
    try:
        data = jwt.decode(raw, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except PyJWTError:
        return None
    if data.get("type") != "pos_operator" or data.get("tenant_id") != tenant_id:
        return None
    row = await db.get(m.PosOperatorSession, str(data.get("sid") or ""))
    if row is None or row.tenant_id != tenant_id or row.user_id != data.get("sub"):
        return None
    if row.ended_at is not None or row.locked_at is not None:
        return None
    return row


async def apply_operator(
    db: AsyncSession, request: Request, *, claims: dict, login_user: m.User
) -> m.User:
    """Return who is acting on this request: the cashier at the till, or the signed-in account.

    Called from ``current_claims`` for every JWT request.
    """
    path = request.url.path
    method = request.method
    raw = (request.headers.get(OPERATOR_HEADER) or "").strip()
    is_lock_api = path.startswith(LOCK_API_PREFIX)
    tenant_id = login_user.tenant_id
    if raw and path_accepts_operator(path):
        row = await _live_row_for_token(db, raw, tenant_id)
        if row is not None and (_now() - row.last_activity_at).total_seconds() > SERVER_IDLE_LIMIT_SECONDS:
            # The browser's own 60-second timer can be switched off. This one cannot.
            await _mark_locked(db, row, reason="server_idle", user_id=row.user_id)
            await db.commit()
            row = None
        if row is None:
            if is_lock_api:
                return login_user
            raise _locked_error()
        operator = await db.get(m.User, row.user_id)
        if operator is None or operator.tenant_id != tenant_id or not operator.is_active:
            if is_lock_api:
                return login_user
            raise _locked_error("That cashier can no longer use this till.")
        claims["login_user_id"] = login_user.id
        claims["pos_operator_session_id"] = row.id
        claims["pos_device_id"] = row.device_id
        claims["sub"] = operator.id
        return operator
    if path_needs_unlocked_till(method, path) and await enforcement_on(db, tenant_id):
        raise _locked_error()
    return login_user


# ---------- throttle ----------


def _throttle_scopes(device_id: str, login_user_id: str) -> list[tuple[str, int, int]]:
    return [
        (f"device:{device_id}", DEVICE_FAIL_LIMIT, DEVICE_LOCK_SECONDS),
        # A till id comes from the browser, so a guesser could keep changing it.
        (f"account:{login_user_id}", ACCOUNT_FAIL_LIMIT, ACCOUNT_LOCK_SECONDS),
    ]


async def _throttle_row(db: AsyncSession, tenant_id: str, scope: str) -> m.PosUnlockThrottle | None:
    return (
        await db.execute(
            select(m.PosUnlockThrottle)
            .where(m.PosUnlockThrottle.tenant_id == tenant_id, m.PosUnlockThrottle.scope_key == scope)
            .with_for_update()
        )
    ).scalar_one_or_none()


def _throttled_error(seconds: int) -> HTTPException:
    minutes = max(1, -(-seconds // 60))
    word = "minute" if minutes == 1 else "minutes"
    return HTTPException(
        status_code=429,
        detail={
            "code": "POS_UNLOCK_THROTTLED",
            "message": f"Too many wrong passcodes. Try again in {minutes} {word}.",
            "retry_after_seconds": seconds,
        },
    )


async def assert_not_throttled(db: AsyncSession, tenant_id: str, device_id: str, login_user_id: str) -> None:
    now = _now()
    for scope, _limit, _seconds in _throttle_scopes(device_id, login_user_id):
        row = await _throttle_row(db, tenant_id, scope)
        if row is not None and row.locked_until is not None and row.locked_until > now:
            raise _throttled_error(int((row.locked_until - now).total_seconds()) + 1)


async def _record_failure(db: AsyncSession, tenant_id: str, device_id: str, login_user_id: str) -> int:
    """Count a wrong try and return how many tries this till has left."""
    now = _now()
    left = DEVICE_FAIL_LIMIT
    for scope, limit, seconds in _throttle_scopes(device_id, login_user_id):
        row = await _throttle_row(db, tenant_id, scope)
        if row is None:
            row = m.PosUnlockThrottle(
                tenant_id=tenant_id, scope_key=scope, failed_count=0, window_started_at=now
            )
            db.add(row)
        elif (now - row.window_started_at).total_seconds() > FAIL_WINDOW_SECONDS:
            row.failed_count = 0
            row.window_started_at = now
            row.locked_until = None
        row.failed_count = int(row.failed_count or 0) + 1
        if row.failed_count >= limit:
            row.locked_until = now + timedelta(seconds=seconds)
            row.failed_count = 0
            row.window_started_at = now
            if scope.startswith("device:"):
                left = 0
        elif scope.startswith("device:"):
            left = limit - row.failed_count
    await db.flush()
    return left


async def _clear_failures(db: AsyncSession, tenant_id: str, device_id: str, login_user_id: str) -> None:
    for scope, _limit, _seconds in _throttle_scopes(device_id, login_user_id):
        row = await _throttle_row(db, tenant_id, scope)
        if row is not None:
            row.failed_count = 0
            row.locked_until = None


# ---------- sessions ----------


async def _live_session(
    db: AsyncSession, tenant_id: str, device_id: str, surface: str
) -> m.PosOperatorSession | None:
    return (
        await db.execute(
            select(m.PosOperatorSession)
            .where(
                m.PosOperatorSession.tenant_id == tenant_id,
                m.PosOperatorSession.device_id == device_id,
                m.PosOperatorSession.surface == surface,
                m.PosOperatorSession.ended_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()


async def _audit(
    db: AsyncSession,
    row_or_tenant: m.PosOperatorSession | str,
    *,
    action: str,
    user_id: str | None,
    device_id: str,
    surface: str,
    details: dict | None = None,
) -> None:
    is_row = isinstance(row_or_tenant, m.PosOperatorSession)
    await audit_svc.record_event(
        db,
        tenant_id=row_or_tenant.tenant_id if is_row else row_or_tenant,
        user_id=user_id,
        module="pos",
        action=action,
        entity="pos_operator_session",
        entity_id=row_or_tenant.id if is_row else None,
        details={"device_id": device_id, "surface": surface, **(details or {})},
    )


async def _mark_locked(db: AsyncSession, row: m.PosOperatorSession, *, reason: str, user_id: str | None) -> None:
    if row.locked_at is not None:
        return
    row.locked_at = _now()
    await _audit(
        db, row, action="pos_locked", user_id=user_id, device_id=row.device_id, surface=row.surface,
        details={"reason": reason},
    )


async def _begin_stint(
    db: AsyncSession,
    *,
    tenant_id: str,
    device_id: str,
    surface: str,
    operator: m.User,
    login_user_id: str,
    method: str,
) -> tuple[m.PosOperatorSession, m.User | None]:
    """Unlock for this cashier. Returns the session, and the cashier replaced if any."""
    now = _now()
    live = await _live_session(db, tenant_id, device_id, surface)
    if live is not None and live.user_id == operator.id:
        live.locked_at = None
        live.last_activity_at = now
        live.login_user_id = login_user_id
        live.unlock_method = method
        await _audit(
            db, live, action="pos_unlocked", user_id=operator.id, device_id=device_id, surface=surface,
            details={"method": method},
        )
        return live, None
    replaced = None
    previous_id = None
    if live is not None:
        replaced = await db.get(m.User, live.user_id)
        previous_id = live.id
        live.ended_at = now
        live.end_reason = "switched"
        await db.flush()
    row = m.PosOperatorSession(
        tenant_id=tenant_id,
        surface=surface,
        device_id=device_id,
        user_id=operator.id,
        login_user_id=login_user_id,
        unlock_method=method,
        previous_session_id=previous_id,
        started_at=now,
        last_activity_at=now,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        # Two tabs unlocking the same till at once.
        await db.rollback()
        raise HTTPException(status_code=409, detail="This till just unlocked in another tab. Try again.") from exc
    if replaced is not None:
        await _audit(
            db, row, action="pos_cashier_switched", user_id=operator.id, device_id=device_id, surface=surface,
            details={
                "from_user_id": replaced.id,
                "from_name": replaced.full_name,
                "to_user_id": operator.id,
                "to_name": operator.full_name,
                "previous_session_id": previous_id,
                "method": method,
            },
        )
    else:
        await _audit(
            db, row, action="pos_unlocked", user_id=operator.id, device_id=device_id, surface=surface,
            details={"method": method},
        )
    return row, replaced


def _operator_view(user: m.User) -> dict:
    return {"id": user.id, "name": user.full_name, "role": user.role}


def _unlock_result(row: m.PosOperatorSession, operator: m.User, replaced: m.User | None) -> dict:
    return {
        "operator_token": issue_operator_token(row),
        "session_id": row.id,
        "operator": _operator_view(operator),
        "switched": replaced is not None,
        "previous_operator": _operator_view(replaced) if replaced is not None else None,
        "idle_seconds": IDLE_LOCK_SECONDS,
    }


async def unlock_with_passcode(
    db: AsyncSession, *, claims: dict, login_user_id: str, device_id: str, surface: str, passcode: str
) -> dict:
    tenant_id = claims["tenant_id"]
    await assert_not_throttled(db, tenant_id, device_id, login_user_id)
    row = (
        await db.execute(
            select(m.PosCashierPasscode).where(
                m.PosCashierPasscode.tenant_id == tenant_id,
                m.PosCashierPasscode.lookup_hash == lookup_hash(tenant_id, passcode),
                m.PosCashierPasscode.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    operator = await db.get(m.User, row.user_id) if row is not None else None
    from app.security import verify_password

    matched = (
        row is not None
        and operator is not None
        and operator.tenant_id == tenant_id
        and operator.is_active
        and verify_password(passcode, row.passcode_hash)
    )
    if not matched:
        left = await _record_failure(db, tenant_id, device_id, login_user_id)
        await _audit(
            db, tenant_id, action="pos_unlock_failed", user_id=login_user_id, device_id=device_id, surface=surface,
            details={"method": "passcode", "tries_left": left},
        )
        await db.commit()
        if left <= 0:
            raise _throttled_error(DEVICE_LOCK_SECONDS)
        raise HTTPException(
            status_code=403,
            detail={"code": "POS_PASSCODE_INVALID", "message": "That passcode is not right.", "tries_left": left},
        )
    if not user_can_use_till(operator, surface):
        await _audit(
            db, tenant_id, action="pos_unlock_denied", user_id=operator.id, device_id=device_id, surface=surface,
            details={"role": operator.role},
        )
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail={"code": "POS_NOT_ALLOWED", "message": f"{operator.full_name} does not have access to this till."},
        )
    await _clear_failures(db, tenant_id, device_id, login_user_id)
    session, replaced = await _begin_stint(
        db, tenant_id=tenant_id, device_id=device_id, surface=surface, operator=operator,
        login_user_id=login_user_id, method="passcode",
    )
    row.last_used_at = _now()
    await restrict_session_to_till(db, claims)
    await db.commit()
    return _unlock_result(session, operator, replaced)


async def lock_till(db: AsyncSession, *, claims: dict, device_id: str, surface: str, reason: str) -> dict:
    tenant_id = claims["tenant_id"]
    row = await _live_session(db, tenant_id, device_id, surface)
    if row is None:
        # A company with no passcodes yet: the signed-in account was selling without a stint.
        row = m.PosOperatorSession(
            tenant_id=tenant_id, surface=surface, device_id=device_id, user_id=claims["sub"],
            login_user_id=claims.get("login_user_id") or claims["sub"], unlock_method="session",
        )
        db.add(row)
        await db.flush()
    await _mark_locked(db, row, reason=reason, user_id=claims["sub"])
    await db.commit()
    return {"locked": True}


async def note_activity(db: AsyncSession, *, claims: dict) -> dict:
    session_id = claims.get("pos_operator_session_id")
    if session_id:
        await db.execute(
            update(m.PosOperatorSession)
            .where(m.PosOperatorSession.id == session_id, m.PosOperatorSession.tenant_id == claims["tenant_id"])
            .values(last_activity_at=_now())
        )
        await db.commit()
    return {"ok": True}


async def till_state(db: AsyncSession, *, claims: dict, device_id: str, surface: str) -> dict:
    tenant_id = claims["tenant_id"]
    enforced = await enforcement_on(db, tenant_id)
    session_id = claims.get("pos_operator_session_id")
    live = (
        await db.execute(
            select(m.PosOperatorSession).where(
                m.PosOperatorSession.tenant_id == tenant_id,
                m.PosOperatorSession.device_id == device_id,
                m.PosOperatorSession.surface == surface,
                m.PosOperatorSession.ended_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if session_id and live is not None and live.id == session_id:
        locked = False
    else:
        locked = enforced
    last = await db.get(m.User, live.user_id) if live is not None else None
    tenant = await db.get(m.Tenant, tenant_id)
    from app import logo_media as logo_media_svc

    logo_key = getattr(tenant, "logo_url", None)
    return {
        "enforced": enforced,
        "locked": locked,
        "login_user_id": claims.get("login_user_id") or claims["sub"],
        "idle_seconds": IDLE_LOCK_SECONDS,
        "passcode_length": PASSCODE_LENGTH,
        "operator": _operator_view(last) if last is not None and not locked else None,
        "last_operator": _operator_view(last) if last is not None else None,
        "company": {
            "id": tenant_id,
            "name": tenant.company_name if tenant else "",
            "has_logo": bool(logo_key),
            "logo_version": logo_media_svc.logo_version(tenant_id, logo_key) if logo_key else None,
        },
    }


async def record_handover(
    db: AsyncSession,
    *,
    claims: dict,
    device_id: str,
    surface: str,
    from_user_id: str,
    decision: str,
    item_count: int,
    total: float,
) -> dict:
    """Write down who answered for a sale that another cashier left on the till."""
    tenant_id = claims["tenant_id"]
    if not claims.get("pos_operator_session_id"):
        raise _locked_error()
    owner = await db.get(m.User, from_user_id)
    if owner is None or owner.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="That cashier was not found")
    await _audit(
        db, tenant_id, action="pos_sale_handover", user_id=claims["sub"], device_id=device_id, surface=surface,
        details={
            "decision": decision,
            "from_user_id": owner.id,
            "from_name": owner.full_name,
            "item_count": item_count,
            "total": total,
        },
    )
    await db.commit()
    return {"decision": decision}


# ---------- admin: passcodes ----------


async def _tenant_user(db: AsyncSession, tenant_id: str, user_id: str) -> m.User:
    user = await db.get(m.User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _passcode_row(db: AsyncSession, tenant_id: str, user_id: str) -> m.PosCashierPasscode | None:
    return (
        await db.execute(
            select(m.PosCashierPasscode).where(
                m.PosCashierPasscode.tenant_id == tenant_id, m.PosCashierPasscode.user_id == user_id
            )
        )
    ).scalar_one_or_none()


async def _code_taken(db: AsyncSession, tenant_id: str, digest: str, *, except_user: str) -> bool:
    found = (
        await db.execute(
            select(m.PosCashierPasscode.id).where(
                m.PosCashierPasscode.tenant_id == tenant_id,
                m.PosCashierPasscode.lookup_hash == digest,
                m.PosCashierPasscode.is_active.is_(True),
                m.PosCashierPasscode.user_id != except_user,
            )
        )
    ).first()
    return found is not None


def _taken_error() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "POS_PASSCODE_TAKEN", "message": "That passcode is already in use. Choose another."},
    )


async def _end_user_stints(db: AsyncSession, tenant_id: str, user_id: str, *, reason: str) -> None:
    now = _now()
    await db.execute(
        update(m.PosOperatorSession)
        .where(
            and_(
                m.PosOperatorSession.tenant_id == tenant_id,
                m.PosOperatorSession.user_id == user_id,
                m.PosOperatorSession.ended_at.is_(None),
            )
        )
        .values(ended_at=now, end_reason=reason)
    )


def _generate_code() -> str:
    while True:
        code = f"{secrets.randbelow(10**PASSCODE_LENGTH):0{PASSCODE_LENGTH}d}"
        if not is_weak_passcode(code):
            return code


def serialize_passcode(row: m.PosCashierPasscode | None) -> dict:
    if row is None:
        return {"status": "none", "updated_at": None, "last_used_at": None}
    return {
        "status": "active" if row.is_active else "inactive",
        "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None,
        "last_used_at": row.last_used_at.isoformat() + "Z" if row.last_used_at else None,
    }


async def list_passcodes(db: AsyncSession, tenant_id: str) -> list[dict]:
    rows = (
        await db.execute(select(m.PosCashierPasscode).where(m.PosCashierPasscode.tenant_id == tenant_id))
    ).scalars().all()
    return [{"user_id": row.user_id, **serialize_passcode(row)} for row in rows]


async def set_passcode(
    db: AsyncSession, *, tenant_id: str, admin_id: str, user_id: str, passcode: str | None
) -> dict:
    """Create or replace a passcode. With no passcode given, generate one and show it once."""
    from app.security import hash_password

    user = await _tenant_user(db, tenant_id, user_id)
    if not user.is_active:
        raise HTTPException(status_code=409, detail="Reactivate this person before giving them a passcode.")
    if not user_can_use_any_till(user):
        raise HTTPException(status_code=409, detail=f"{user.full_name} does not use a till in their role.")
    generated = passcode is None
    if generated:
        for _ in range(20):
            code = _generate_code()
            if not await _code_taken(db, tenant_id, lookup_hash(tenant_id, code), except_user=user.id):
                break
        else:
            raise HTTPException(status_code=503, detail="Could not generate a free passcode. Try again.")
    else:
        code = validate_passcode(passcode)
    digest = lookup_hash(tenant_id, code)
    if await _code_taken(db, tenant_id, digest, except_user=user.id):
        await audit_svc.record_event(
            db, tenant_id=tenant_id, user_id=admin_id, module="pos", action="pos_passcode_rejected_duplicate",
            entity="user", entity_id=user.id, details={},
        )
        await db.commit()
        raise _taken_error()
    now = _now()
    row = await _passcode_row(db, tenant_id, user.id)
    action = "pos_passcode_changed" if row is not None else "pos_passcode_created"
    if row is None:
        row = m.PosCashierPasscode(
            tenant_id=tenant_id, user_id=user.id, lookup_hash=digest, passcode_hash=hash_password(code),
            is_active=True, created_by=admin_id, created_at=now, updated_at=now,
        )
        db.add(row)
    else:
        row.lookup_hash = digest
        row.passcode_hash = hash_password(code)
        row.is_active = True
        row.updated_at = now
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise _taken_error() from exc
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=admin_id, module="pos", action=action,
        entity="user", entity_id=user.id, details={"generated": generated},
    )
    await db.commit()
    body = {"user_id": user.id, **serialize_passcode(row)}
    if generated:
        body["passcode"] = code
    return body


async def set_passcode_active(
    db: AsyncSession, *, tenant_id: str, admin_id: str, user_id: str, is_active: bool
) -> dict:
    user = await _tenant_user(db, tenant_id, user_id)
    row = await _passcode_row(db, tenant_id, user.id)
    if row is None:
        raise HTTPException(status_code=404, detail="This person has no passcode yet.")
    if is_active and await _code_taken(db, tenant_id, row.lookup_hash, except_user=user.id):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "POS_PASSCODE_TAKEN",
                "message": "Another cashier now uses this passcode. Set a new one instead.",
            },
        )
    row.is_active = is_active
    row.updated_at = _now()
    if not is_active:
        await _end_user_stints(db, tenant_id, user.id, reason="passcode_deactivated")
    await audit_svc.record_event(
        db, tenant_id=tenant_id, user_id=admin_id, module="pos",
        action="pos_passcode_activated" if is_active else "pos_passcode_deactivated",
        entity="user", entity_id=user.id, details={},
    )
    await db.commit()
    return {"user_id": user.id, **serialize_passcode(row)}

