"""HTTP mutation audit middleware (Stage 1 G19 / BR-17.1 auto-coverage).

Logs successful POST/PUT/PATCH/DELETE under /api/v1 into the hash-chained audit log.
Explicit `audit.record_event` calls remain the rich domain trail; this catch-all
covers routes that lack a dedicated audit write.
"""

from __future__ import annotations

import logging
import re

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger(__name__)

MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

SKIP_PREFIXES = (
    "/api/v1/audit-logs",
    "/docs",
    "/redoc",
    "/openapi.json",
)

# First path segment after /api/v1/ → audit module
_SEGMENT_MODULE = {
    "auth": "security",
    "users": "users",
    "roles": "users",
    "tenants": "company",
    "settings": "company",
    "me": "security",
    "products": "inventory",
    "inventory": "inventory",
    "warehouses": "stores",
    "stores": "stores",
    "branches": "company",
    "departments": "company",
    "sales": "sales",
    "customers": "sales",
    "pos": "pos",
    "purchasing": "purchasing",
    "suppliers": "purchasing",
    "expenses": "expenses",
    "accounting": "accounting",
    "credit": "credit",
    "tax": "tax",
    "reports": "reports",
    "notifications": "notifications",
    "backup": "backup",
    "ai": "ai",
    "dashboard": "dashboard",
}

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def module_from_path(path: str) -> str:
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return _SEGMENT_MODULE.get(parts[2], parts[2][:40] or "system")
    return "system"


def entity_from_path(path: str) -> tuple[str, str | None]:
    """Return (entity_label, entity_id) from trailing UUID when present."""
    parts = [p for p in path.split("/") if p]
    entity_id = None
    if parts and _UUID_RE.match(parts[-1]):
        entity_id = parts[-1]
        label_parts = parts[:-1]
    else:
        label_parts = parts
    # Prefer /api/v1/<seg>/...
    if len(label_parts) >= 3 and label_parts[0] == "api":
        entity = "/".join(label_parts[2:])[:100] or "api"
    else:
        entity = "/".join(label_parts)[:100] or "api"
    return entity, entity_id


def peek_access_claims(request: Request) -> dict | None:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        data = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
    if data.get("type") and data.get("type") != "access":
        return None
    if not data.get("tenant_id") or not data.get("sub"):
        return None
    return data


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return (request.client.host or "")[:64] or None
    return None


class AuditMutationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if not getattr(settings, "AUDIT_HTTP_MIDDLEWARE_ENABLED", True):
            return response
        try:
            await self._maybe_record(request, response)
        except Exception:  # noqa: BLE001 — never break the response for audit
            logger.exception("Audit mutation middleware failed")
        return response

    async def _maybe_record(self, request: Request, response: Response) -> None:
        if request.method not in MUTATING:
            return
        path = request.url.path or ""
        if not path.startswith("/api/v1/"):
            return
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return
        # Only successful / completed writes (exclude client/auth failures).
        if response.status_code < 200 or response.status_code >= 400:
            return

        claims = peek_access_claims(request)
        tenant_id = (claims or {}).get("tenant_id") or request.headers.get("X-Tenant-ID")
        if not tenant_id:
            return
        user_id = (claims or {}).get("sub")
        # Prefer verified request.state.company_id from auth; never invent from untrusted headers alone.
        company_id = getattr(request.state, "company_id", None)
        entity, entity_id = entity_from_path(path)
        module = module_from_path(path)

        from app import audit as audit_svc
        from app.db import SessionLocal

        # Tests (and alternate engines) may inject app.state.session_factory.
        session_factory = getattr(request.app.state, "session_factory", None) or SessionLocal

        async with session_factory() as db:
            await audit_svc.record_event(
                db,
                tenant_id=tenant_id,
                user_id=user_id,
                company_id=company_id,
                module=module,
                action="http_write",
                entity=entity,
                entity_id=entity_id,
                details={
                    "method": request.method,
                    "path": path[:300],
                    "status_code": response.status_code,
                    "source": "audit_middleware",
                },
                ip_address=client_ip(request),
                user_agent=(request.headers.get("user-agent") or "")[:255] or None,
            )
            await db.commit()
