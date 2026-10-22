"""Safe HTTP error responses. Diagnostics stay in server logs only."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, ProgrammingError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ribdigi.http")

SAFE_500 = "The server could not complete this request."
SAFE_409 = "That record already exists."
TENANT_CREATE_SLUG_EXISTS = "That workspace slug is already in use."
TENANT_CREATE_EMAIL_EXISTS = "That admin email is already used on this workspace."
TENANT_CREATE_CONSTRAINT = "That workspace slug or admin email already exists."
TENANT_CREATE_SCHEMA = (
    "Could not create the workspace because the database is missing a required field. "
    "Nothing was saved. Contact Ribdigi support."
)
TENANT_CREATE_UNAVAILABLE = (
    "Could not create the workspace because the database was busy or unreachable. "
    "Nothing was saved. Try again."
)
TENANT_CREATE_FAILED = (
    "Could not create the workspace. Nothing was saved. "
    "Try a different slug or email, or contact Ribdigi support."
)


class TenantSeedError(RuntimeError):
    """Seed step failed; `step` is a short user-safe label (no SQL)."""

    def __init__(self, step: str):
        self.step = step
        super().__init__(step)


def tenant_seed_failed_message(step: str) -> str:
    label = (step or "defaults").strip()[:80]
    return f"Could not finish workspace setup ({label}). Nothing was saved. Try again or contact Ribdigi support."


def http_exception_for_tenant_create_failure(exc: BaseException) -> HTTPException:
    """Map tenant-create failures to a safe client message. SQL stays in logs."""
    probe: BaseException = exc
    if isinstance(exc, TenantSeedError) and exc.__cause__ is not None:
        probe = exc.__cause__
    if isinstance(probe, IntegrityError):
        raw = str(getattr(probe, "orig", None) or probe).lower()
        if "tenants.slug" in raw or "ix_tenants_slug" in raw or "tenants_slug" in raw:
            return HTTPException(status_code=409, detail=TENANT_CREATE_SLUG_EXISTS)
        if "users.email" in raw or "ix_users_email" in raw or "users_email" in raw:
            return HTTPException(status_code=409, detail=TENANT_CREATE_EMAIL_EXISTS)
        if isinstance(exc, TenantSeedError):
            return HTTPException(status_code=500, detail=tenant_seed_failed_message(exc.step))
        return HTTPException(status_code=409, detail=TENANT_CREATE_CONSTRAINT)
    if isinstance(probe, ProgrammingError):
        return HTTPException(status_code=500, detail=TENANT_CREATE_SCHEMA)
    if isinstance(probe, OperationalError):
        return HTTPException(status_code=503, detail=TENANT_CREATE_UNAVAILABLE)
    if isinstance(probe, DataError):
        return HTTPException(status_code=400, detail="One of the workspace fields is not valid for the database.")
    if isinstance(exc, TenantSeedError):
        return HTTPException(status_code=500, detail=tenant_seed_failed_message(exc.step))
    return HTTPException(status_code=500, detail=TENANT_CREATE_FAILED)


def _field_detail(field: str, message: str) -> list[dict]:
    return [{"loc": ["body", field], "msg": message, "type": "value_error"}]


def _missing_related_detail(raw: str, path: str = ""):
    """Map constraint text to a field message. SQL stays in logs only."""
    path = (path or "").lower()
    if "customer_group" in raw:
        return _field_detail(
            "customer_group",
            "Customer group was not found or is not available in this company.",
        )
    if "company_id" in raw or ("companies" in raw and "foreign" in raw):
        return _field_detail(
            "company",
            "Company is required. Create a company for this workspace, then try again.",
        )
    if "tenant_id" in raw or "tenants." in raw:
        return "Workspace is missing or not available."
    if "store_id" in raw or "stores." in raw:
        return _field_detail("store", "Store was not found or is not available.")
    if "/customers" in path:
        return (
            "Could not save the customer. Check that company and customer group "
            "exist for this workspace."
        )
    return "Could not save because a required related record is missing."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.exception(
            "database constraint failed method=%s path=%s",
            request.method,
            request.url.path,
        )
        raw = str(getattr(exc, "orig", None) or exc).lower()
        if "foreign key" in raw or "not null" in raw or "not-null" in raw or "null value" in raw:
            return JSONResponse(
                status_code=400,
                content={"detail": _missing_related_detail(raw, request.url.path)},
            )
        return JSONResponse(status_code=409, content={"detail": SAFE_409})

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        rid = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
        logger.exception(
            "database error method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            rid,
        )
        body: dict = {"detail": SAFE_500}
        if rid:
            body["request_id"] = str(rid)
        return JSONResponse(status_code=500, content=body)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (HTTPException, StarletteHTTPException, RequestValidationError)):
            raise exc
        rid = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
        logger.exception(
            "unhandled error method=%s path=%s request_id=%s",
            request.method,
            request.url.path,
            rid,
        )
        body: dict = {"detail": SAFE_500}
        if rid:
            body["request_id"] = str(rid)
        return JSONResponse(status_code=500, content=body)
