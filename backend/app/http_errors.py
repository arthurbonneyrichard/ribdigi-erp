"""Safe HTTP error responses. Diagnostics stay in server logs only."""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("ribdigi.http")

SAFE_500 = "The server could not complete this request."
SAFE_409 = "That record already exists."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.exception(
            "database constraint failed method=%s path=%s",
            request.method,
            request.url.path,
        )
        return JSONResponse(status_code=409, content={"detail": SAFE_409})

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception(
            "database error method=%s path=%s",
            request.method,
            request.url.path,
        )
        return JSONResponse(status_code=500, content={"detail": SAFE_500})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, (HTTPException, StarletteHTTPException, RequestValidationError)):
            raise exc
        logger.exception(
            "unhandled error method=%s path=%s",
            request.method,
            request.url.path,
        )
        return JSONResponse(status_code=500, content={"detail": SAFE_500})
