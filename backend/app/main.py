from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import api
from app.audit_middleware import AuditMutationMiddleware
from app.config import settings
from app.db import SessionLocal
from app.http_errors import register_exception_handlers
from app.middleware import MetricsMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.request_logging import RequestLoggingMiddleware
import logging

is_prod = is_production()
_docs = openapi_enabled()

# Stage 18 L1 — apply LOG_LEVEL for structured request logger (and root if unset).
_level = getattr(logging, str(settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
logging.getLogger("ribdigi.request").setLevel(_level)
if not logging.getLogger().handlers:
    logging.basicConfig(level=_level)

_level = getattr(logging, str(settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
logging.getLogger("ribdigi.request").setLevel(_level)
if not logging.getLogger().handlers:
    logging.basicConfig(level=_level)

app = FastAPI(
    title="RIBDIGI BUSINESS ERP API",
    version=settings.APP_VERSION or "1.0.0",
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
        "Content-Disposition",
        "Content-Type",
    ],
    "max_age": 600,
}
app.add_middleware(CORSMiddleware, **cors_kwargs)
# Outer logging so latency includes rate-limit / audit middleware and X-Request-ID is always set.
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api)
register_exception_handlers(app)
# Used by AuditMutationMiddleware (overridable in tests via app.state.session_factory).
app.state.session_factory = SessionLocal


@app.on_event("startup")
async def _align_hybrid_schema_on_startup() -> None:
    if settings.APP_ENV.lower() != "production":
        return
    if "sqlite" in (settings.DATABASE_URL or "").lower():
        return
    from app.db import engine
    from app.schema_align import align_async_engine

    try:
        await align_async_engine(engine)
    except Exception:
        logging.getLogger("ribdigi.schema_align").exception("startup schema align failed")


@app.get("/")
async def root():
    return {
        "name": "RIBDIGI BUSINESS ERP",
        "version": settings.APP_VERSION or "1.0.0",
        "build_id": (settings.APP_BUILD_ID or "").strip() or None,
        "docs": "/docs" if openapi_enabled() else None,
    }
