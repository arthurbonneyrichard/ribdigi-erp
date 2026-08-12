from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import api
from app.audit_middleware import AuditMutationMiddleware
from app.config import settings
from app.db import SessionLocal
from app.middleware import MetricsMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.request_logging import RequestLoggingMiddleware
import logging

is_prod = settings.APP_ENV.lower() == "production"

_level = getattr(logging, str(settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
logging.getLogger("ribdigi.request").setLevel(_level)
if not logging.getLogger().handlers:
    logging.basicConfig(level=_level)

app = FastAPI(
    title="RIBDIGI BUSINESS ERP API",
    version="1.0.0",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
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
# Used by AuditMutationMiddleware (overridable in tests via app.state.session_factory).
app.state.session_factory = SessionLocal


@app.get("/")
async def root():
    return {"name": "RIBDIGI BUSINESS ERP", "version": "1.0.0", "docs": None if is_prod else "/docs"}
