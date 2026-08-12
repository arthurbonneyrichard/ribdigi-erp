from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api import api
from app.audit_middleware import AuditMutationMiddleware
from app.config import settings
from app.db import SessionLocal
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

is_prod = settings.APP_ENV.lower() == "production"

app = FastAPI(
    title="RIBDIGI BUSINESS ERP API",
    version="1.0.0",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

# Middleware order: last added runs first on request.
app.add_middleware(SecurityHeadersMiddleware)
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
        "Accept",
        "Origin",
    ],
    "expose_headers": [
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Backend",
        "Retry-After",
    ],
    "max_age": 600,
}
app.add_middleware(CORSMiddleware, **cors_kwargs)

app.include_router(api)
# Used by AuditMutationMiddleware (overridable in tests via app.state.session_factory).
app.state.session_factory = SessionLocal


@app.get("/")
async def root():
    return {"name": "RIBDIGI BUSINESS ERP", "version": "1.0.0", "docs": None if is_prod else "/docs"}
