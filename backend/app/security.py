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
from app.rbac import (
    VALID_ROLES,
    has_permission,
    permissions_for_role,
    record_scope_from_permissions,
)

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


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    jti: str | None = None,
    *,
    principal: str | None = None,
) -> str:
    from app.platform_const import principal_for

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "principal": principal or principal_for(tenant_id=tenant_id, role=role),
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
        "principal": "tenant",
        "type": "api_key",
        "permissions": row.permissions or {},
        "email_verified": True,
        "totp_enabled": False,
        "webauthn_enabled": False,
        "must_enroll_2fa": False,
        "tenant_status": tenant.status,
        "read_only": tenants_svc.is_read_only(tenant),
        "branch_id": None,
        "department_id": None,
        "record_scope": "all",
        "scope_user_ids": [],
        "auth_method": "api_key",
        "api_key_id": row.id,
    }
    request.state.user_id = claims["sub"]
    request.state.tenant_id = tenant_id
    request.state.api_key_id = row.id
    return claims


async def resolve_user_permissions(db: AsyncSession, user: m.User) -> dict:
    """Resolve effective permissions with optional Redis/app-cache (Stage 7 C2).

    Soft-fails when cache is disabled or Redis is down (same pattern as P2).
    """
    from app.cache import app_cache

    key = app_cache.permissions_key(user.tenant_id, user.id)
    cached = await app_cache.get_json(key)
    if isinstance(cached, dict):
        return cached

    if isinstance(user.permissions, dict) and user.permissions:
        perms = dict(user.permissions)
    elif user.role in VALID_ROLES:
        perms = permissions_for_role(user.role)
    else:
        from app import roles as roles_svc

        try:
            perms = await roles_svc.permissions_for_assignment(
                db, user.tenant_id, user.role
            )
        except Exception:
            perms = {}

    if not isinstance(perms, dict):
        perms = {}
    await app_cache.set_json(
        key, perms, ttl_seconds=int(settings.CACHE_PERMISSIONS_TTL_SECONDS)
    )
    return perms


async def current_claims(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_workspace_kind: str | None = Header(default=None, alias="X-Workspace-Kind"),
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    raw_api_key = (x_api_key or "").strip()
    if not raw_api_key and creds and str(creds.credentials or "").startswith("rdk_"):
        raw_api_key = str(creds.credentials).strip()
    if raw_api_key:
        claims = await _claims_from_api_key(request, db, raw_api_key, x_tenant_id)
        # API keys operate in company workspace on the tenant default company (ADR-490).
        from app import workspace as workspace_svc

        tenant = await db.get(m.Tenant, claims["tenant_id"])
        if tenant:
            co = await workspace_svc.ensure_default_company(db, tenant)
            claims["workspace_kind"] = "company"
            claims["company_id"] = co.id
        else:
            claims["workspace_kind"] = "company"
            claims["company_id"] = None
        request.state.workspace_kind = claims.get("workspace_kind")
        request.state.company_id = claims.get("company_id")
        return claims

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
    from app.platform_const import (
        is_platform_tenant_id,
        path_allowed_for_platform_principal,
        principal_for,
    )

    tenant = await tenants_svc.ensure_trial_state(db, tenant)
    # Prefer live role/tenant over stale JWT principal
    live_principal = principal_for(tenant_id=tenant_id, role=str(user.role or ""))
    if tenant.status == "suspended" and not (
        is_platform_tenant_id(tenant_id) and live_principal == "platform"
    ):
        raise HTTPException(status_code=403, detail="Tenant suspended or missing")

    data["permissions"] = await resolve_user_permissions(db, user)
    data["email_verified"] = user.email_verified
    data["totp_enabled"] = bool(user.totp_enabled)
    data["tenant_status"] = tenant.status
    data["read_only"] = tenants_svc.is_read_only(tenant)
    data["branch_id"] = getattr(user, "branch_id", None)
    data["department_id"] = getattr(user, "department_id", None)
    data["auth_method"] = "jwt"
    data["principal"] = live_principal
    data["role"] = user.role
    if live_principal == "platform" and not path_allowed_for_platform_principal(request.url.path):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PLATFORM_USE_PLATFORM_API",
                "message": "Platform principals cannot access tenant ERP modules. Use /api/v1/platform/*.",
            },
        )
    scope = record_scope_from_permissions(
        user.role, data["permissions"] if isinstance(data.get("permissions"), dict) else None
    )
    data["record_scope"] = scope
    from app import org_units as org_units_svc

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
    # ADR-490 — workspace context (tenant vs company). Never trust client company_id alone.
    if live_principal != "platform":
        from app import workspace as workspace_svc

        ws = await workspace_svc.resolve_workspace(
            db,
            tenant=tenant,
            user=user,
            requested_kind=x_workspace_kind,
            requested_company_id=x_company_id,
        )
        data["workspace_kind"] = ws["workspace_kind"]
        data["company_id"] = ws.get("company_id")
        # When in company workspace, membership role/permissions may refine effective RBAC.
        if ws["workspace_kind"] == "company" and ws.get("membership_permissions"):
            data["permissions"] = ws["membership_permissions"]
        elif ws["workspace_kind"] == "company" and ws.get("membership_role"):
            mem_role = ws["membership_role"]
            # Prefer explicit membership role map when user.permissions empty.
            if not data.get("permissions"):
                from app.rbac import permissions_for_role

                data["permissions"] = permissions_for_role(mem_role)
            data["membership_role"] = mem_role
        if ws["workspace_kind"] == "tenant" and is_tenant_admin_like(user.role):
            # Tenant workspace: strip operational wildcards for non-platform tenant admins
            # by keeping permissions but gating modules in require_permission via workspace.
            data["tenant_admin"] = True
    else:
        data["workspace_kind"] = "platform"
        data["company_id"] = None

    request.state.user_id = user_id
    request.state.tenant_id = tenant_id
    request.state.principal = data["principal"]
    request.state.workspace_kind = data.get("workspace_kind")
    request.state.company_id = data.get("company_id")
    return data


def is_tenant_admin_like(role: str | None) -> bool:
    from app.workspace import is_tenant_admin_role

    return is_tenant_admin_role(role)


def require_roles(*roles: str):
    async def dep(claims: dict = Depends(current_claims)) -> dict:
        if claims.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permission")
        return claims

    return dep


def require_platform_permission(module: str, action: str = "read"):
    """Authorize Ribdigi House platform APIs (ADR-137)."""

    async def dep(claims: dict = Depends(current_claims)) -> dict:
        if claims.get("principal") != "platform":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PLATFORM_PRINCIPAL_REQUIRED",
                    "message": "Platform administration requires a Ribdigi House platform principal.",
                },
            )
        role = claims.get("role", "")
        overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
        if overrides and (overrides.get("*") == ["*"] or "*" in (overrides.get("*") or [])):
            return claims
        if not has_permission(role, module, action, overrides=overrides):
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {module}:{action}",
            )
        return claims

    return dep


def require_permission(module: str, action: str = "read"):
    async def dep(claims: dict = Depends(current_claims)) -> dict:
        # Defense in depth — allowlist already enforced in current_claims for platform.
        if claims.get("principal") == "platform" and module not in {"security"}:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PLATFORM_USE_PLATFORM_API",
                    "message": "Platform principals cannot access tenant ERP modules. Use /api/v1/platform/*.",
                },
            )
        if claims.get("read_only") and action != "read":
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "TENANT_READ_ONLY",
                    "message": "Trial expired; account is read-only during the grace period. Activate to restore write access.",
                },
            )
        # ADR-490 — operational modules require company workspace + membership.
        from app import workspace as workspace_svc

        workspace_svc.assert_module_workspace(claims, module)

        role = claims.get("role", "")
        overrides = claims.get("permissions") if isinstance(claims.get("permissions"), dict) else None
        # Tenant workspace: tenant admins may manage companies/subscription without ops wildcards.
        if claims.get("workspace_kind") == "tenant" and module in {
            "tenant_dashboard",
            "companies",
            "subscription",
            "tenant",
            "security",
            "users",
            "backup",
        }:
            if is_tenant_admin_like(role) or has_permission(role, module, action, overrides=overrides):
                return claims
        if overrides and (overrides.get("*") == ["*"] or "*" in (overrides.get("*") or [])):
            return claims
        # user.permissions is the authoritative map (system copy or custom role snapshot).
        if not has_permission(role, module, action, overrides=overrides):
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {module}:{action}",
            )
        return claims

    return dep


# Backwards-compatible alias used by older call sites
def token(user_id: str, tenant_id: str, role: str, minutes: int | None = None) -> str:
    return create_access_token(user_id, tenant_id, role)
