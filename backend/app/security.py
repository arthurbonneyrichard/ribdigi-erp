from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app import models as m
from app.rbac import has_permission, is_system_role, permissions_for_role, is_platform_role

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer(auto_error=False)

PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$")


def hash_password(value: str) -> str:
    return pwd.hash(value)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd.verify(raw, hashed)


def validate_password_strength(password: str) -> None:
    if not PASSWORD_PATTERN.match(password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters and include upper, lower, number, and symbol",
        )


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_access_token(user_id: str, tenant_id: str, role: str, jti: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "jti": jti or secrets.token_hex(16),
        "iat": int(now.timestamp()),
        "exp": exp,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def issue_refresh_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(48)
    expires = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return raw, hash_token(raw), expires


def issue_one_time_token() -> tuple[str, str, datetime]:
    raw = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=1)
    return raw, hash_token(raw), expires


async def _claims_from_api_key(
    request: Request,
    db: AsyncSession,
    raw_key: str,
    x_tenant_id: str | None,
) -> dict:
    from app import api_keys as api_keys_svc
    from app import tenants as tenants_svc
    from app import packages as packages_svc

    row = await api_keys_svc.authenticate_api_key(db, raw_key)
    tenant_id = row.tenant_id
    if x_tenant_id and x_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=403, detail="Tenant suspended or missing")
    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    if tenant.status == "suspended":
        raise HTTPException(status_code=403, detail="Tenant suspended or missing")

    claims = {
        "sub": f"apikey:{row.id}",
        "tenant_id": tenant_id,
        "role": "api_key",
        "type": "api_key",
        "permissions": row.permissions or {},
        "email_verified": True,
        "totp_enabled": False,
        "webauthn_enabled": False,
        "must_enroll_2fa": False,
        "tenant_status": tenant.status,
        "read_only": tenants_svc.is_read_only(tenant),
        "package_code": getattr(tenant, "package_code", None) or "trial",
        "enabled_modules": packages_svc.resolve_enabled_modules(tenant),
        "branch_id": None,
        "department_id": None,
        "record_scope": "all",
        "scope_user_ids": None,
        "auth_method": "api_key",
        "api_key_id": row.id,
    }
    request.state.user_id = claims["sub"]
    request.state.tenant_id = tenant_id
    request.state.api_key_id = row.id
    return claims


async def current_claims(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_api_key = (x_api_key or "").strip()
    if not raw_api_key and creds and str(creds.credentials or "").startswith("rdk_"):
        raw_api_key = str(creds.credentials).strip()
    if raw_api_key:
        return await _claims_from_api_key(request, db, raw_api_key, x_tenant_id)

    if not creds:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        data = jwt.decode(creds.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    if data.get("type") and data.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")

    tenant_id = data.get("tenant_id")
    user_id = data.get("sub")
    if not tenant_id or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    if x_tenant_id and x_tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")

    jti = data.get("jti")
    if jti:
        session = (
            await db.execute(
                select(m.AuthSession).where(
                    m.AuthSession.jti == jti,
                    m.AuthSession.tenant_id == tenant_id,
                    m.AuthSession.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if session and session.revoked_at is not None:
            raise HTTPException(status_code=401, detail="Session revoked")

    user = (
        await db.execute(
            select(m.User).where(
                m.User.id == user_id,
                m.User.tenant_id == tenant_id,
                m.User.is_active == True,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    tenant = await db.get(m.Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=403, detail="Tenant suspended or missing")
    from app import tenants as tenants_svc

    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    if tenant.status == "suspended":
        raise HTTPException(status_code=403, detail="Tenant suspended or missing")

    data["permissions"] = user.permissions or permissions_for_role(user.role)
    data["email_verified"] = user.email_verified
    data["totp_enabled"] = bool(user.totp_enabled)
    data["tenant_status"] = tenant.status
    data["read_only"] = tenants_svc.is_read_only(tenant)
    from app import packages as packages_svc

    data["package_code"] = getattr(tenant, "package_code", None) or "trial"
    data["enabled_modules"] = packages_svc.resolve_enabled_modules(tenant)
    data["branch_id"] = getattr(user, "branch_id", None)
    data["department_id"] = getattr(user, "department_id", None)
    from app.rbac import record_scope_from_permissions
    from app import org_units as org_units_svc

    scope = record_scope_from_permissions(
        user.role, data["permissions"] if isinstance(data["permissions"], dict) else None
    )
    data["record_scope"] = scope
    data["scope_user_ids"] = await org_units_svc.scope_user_ids(
        db, tenant_id=tenant_id, user=user, scope=scope
    )
    from app.totp import path_allowed_during_enrollment, role_requires_2fa
    from app import webauthn_svc as webauthn

    has_mfa = await webauthn.user_has_mfa(db, user)
    data["webauthn_enabled"] = await webauthn.user_has_webauthn(db, user.id)
    must_enroll = role_requires_2fa(user.role) and not has_mfa
    data["must_enroll_2fa"] = must_enroll
    if must_enroll and not path_allowed_during_enrollment(request.url.path):
        raise HTTPException(
            status_code=403,
            detail="2FA enrollment required for this role. Complete setup at /security",
        )
    request.state.user_id = user_id
    request.state.tenant_id = tenant_id
    return data


def require_roles(*roles: str):
    async def dep(claims: dict = Depends(current_claims)) -> dict:
        if claims.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return claims

    return dep


def require_platform_permission(module: str, action: str = "read"):
    """Gate software-owner console APIs (platform staff roles only)."""

    async def dep(claims: dict = Depends(current_claims)) -> dict:
        role = claims.get("role") or ""
        if not is_platform_role(role):
            raise HTTPException(status_code=403, detail="Platform staff access required")
        overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
        if overrides and overrides.get("*") == ["*"]:
            return claims
        if not has_permission(role, module, action, overrides=overrides):
            raise HTTPException(
                status_code=403,
                detail=f"Missing platform permission: {module}:{action}",
            )
        return claims

    return dep


def require_permission(module: str, action: str = "read"):
    async def dep(claims: dict = Depends(current_claims)) -> dict:
        if claims.get("read_only") and action != "read":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "TENANT_READ_ONLY",
                    "message": "Trial expired; account is read-only during the grace period. Activate to restore write access.",
                },
            )
        # Package feature gate (software-owner controlled modules)
        if not is_platform_role(claims.get("role")):
            from app import packages as packages_svc

            mod = (module or "").strip().lower()
            enabled = claims.get("enabled_modules")
            if (
                enabled is not None
                and mod
                and mod not in packages_svc.ALWAYS_ON_MODULES
                and mod != "platform"
                and not mod.startswith("platform_")
                and mod not in enabled
            ):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "PACKAGE_FEATURE_DISABLED",
                        "message": f"Module '{mod}' is not included in this tenant's package",
                        "module": mod,
                        "package_code": claims.get("package_code"),
                    },
                )
        role = claims.get("role", "")
        overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
        # permissions in claims may be the full map from user; treat wildcard user override specially
        if overrides and overrides.get("*") == ["*"]:
            return claims
        # Custom roles: evaluate against the full stored permission map.
        if not is_system_role(role):
            if not has_permission(role, module, action, overrides=overrides):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {module}:{action}",
                )
            return claims
        user_overrides = None
        if overrides and module in overrides:
            user_overrides = {module: overrides[module]}
        if not has_permission(role, module, action, overrides=user_overrides if user_overrides else overrides):
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {module}:{action}",
            )
        return claims

    return dep


# Backwards-compatible alias used by older call sites
def token(user_id: str, tenant_id: str, role: str, minutes: int | None = None) -> str:
    return create_access_token(user_id, tenant_id, role)
