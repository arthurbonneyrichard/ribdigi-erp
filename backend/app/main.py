from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import api
from app.config import settings
from app.audit_middleware import AuditMutationMiddleware
from app.db import SessionLocal
from app.middleware import MetricsMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.platform_api import router as platform_api
from app.request_logging import RequestLoggingMiddleware
from app.security_runtime import is_production, openapi_enabled
import logging

is_prod = is_production()
_docs = openapi_enabled()

# Stage 18 L1 — apply LOG_LEVEL for structured request logger (and root if unset).
_level = getattr(logging, str(settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
logging.getLogger("ribdigi.request").setLevel(_level)
if not logging.getLogger().handlers:
    logging.basicConfig(level=_level)

app = FastAPI(
    title="RIBDIGI BUSINESS ERP API",
    version="1.0.0",
    docs_url="/docs" if _docs else None,
    redoc_url="/redoc" if _docs else None,
    openapi_url="/openapi.json" if _docs else None,
)

# Middleware order: last added runs first on request.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuditMutationMiddleware)

if settings.trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

cors_kwargs = {
    "allow_origins": settings.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "X-Tenant-ID",
        "X-API-Key",
        "X-Request-ID",
        "Accept",
        "Origin",
    ],
    "expose_headers": [
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Backend",
        "Retry-After",
        "X-Request-ID",
    ],
    "max_age": 600,
}
app.add_middleware(CORSMiddleware, **cors_kwargs)
# Outer logging so latency includes rate-limit / audit middleware and X-Request-ID is always set.
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api)
app.include_router(platform_api)
# Used by AuditMutationMiddleware (overridable in tests via app.state.session_factory).
app.state.session_factory = SessionLocal


@app.get("/")
async def root():
    return {
        "name": "RIBDIGI BUSINESS ERP",
        "version": "1.0.0",
        "docs": "/docs" if openapi_enabled() else None,
    }
