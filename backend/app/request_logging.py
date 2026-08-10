"""Stage 18 L1 — structured JSON request/error logs (MVP-lite; no Grafana/PagerDuty)."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from jose import JWTError, jwt
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings

logger = logging.getLogger("ribdigi.request")

REQUEST_ID_HEADER = "X-Request-ID"
_SKIP_PATH_PREFIXES = (
    "/api/v1/health",
    "/api/v1/metrics",
)
_SAFE_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,64}$")


def request_log_enabled() -> bool:
    return bool(getattr(settings, "REQUEST_LOG_ENABLED", True))


def new_request_id() -> str:
    return uuid.uuid4().hex


def resolve_request_id(request: Request) -> str:
    incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
    if incoming and len(incoming) <= 128 and all(c.isalnum() or c in "-_" for c in incoming):
        return incoming
    return new_request_id()


def _safe_error_code_from_detail(detail: Any) -> str | None:
    if isinstance(detail, dict):
        code = detail.get("code") or detail.get("detail")
        if isinstance(code, str) and _SAFE_CODE_RE.match(code):
            return code
        return None
    if isinstance(detail, str):
        text = detail.strip()
        if _SAFE_CODE_RE.match(text):
            return text
        # First token of messages like "INSUFFICIENT_STOCK: ..."
        token = text.split(":", 1)[0].strip()
        if _SAFE_CODE_RE.match(token):
            return token
    return None


def safe_error_code(*, status_code: int, response: Response | None = None) -> str | None:
    """Return a non-PII error code for failed responses."""
    if status_code < 400:
        return None
    if response is not None:
        raw = getattr(response, "body", None)
        if raw:
            try:
                if isinstance(raw, memoryview):
                    raw = raw.tobytes()
                if isinstance(raw, (bytes, bytearray)):
                    payload = json.loads(raw.decode("utf-8"))
                elif isinstance(raw, str):
                    payload = json.loads(raw)
                else:
                    payload = None
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError):
                payload = None
            if isinstance(payload, dict):
                for key in ("detail", "code", "message"):
                    code = _safe_error_code_from_detail(payload.get(key))
                    if code:
                        return code
                nested = payload.get("data")
                if isinstance(nested, dict):
                    code = _safe_error_code_from_detail(nested.get("code") or nested.get("detail"))
                    if code:
                        return code
    defaults = {
        400: "BAD_REQUEST",
        401: "UNAUTHENTICATED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMIT_EXCEEDED",
        500: "INTERNAL_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return defaults.get(status_code, f"HTTP_{status_code}")


def peek_auth_context(request: Request) -> tuple[str | None, str | None]:
    """Best-effort tenant_id / user_id for logs — never raises."""
    tenant_id = (request.headers.get("X-Tenant-ID") or "").strip() or None
    user_id: str | None = None
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        if token and not token.startswith("rdk_"):
            try:
                data = jwt.decode(
                    token,
                    settings.JWT_SECRET_KEY,
                    algorithms=[settings.JWT_ALGORITHM],
                )
                if not data.get("type") or data.get("type") == "access":
                    user_id = data.get("sub")
                    tenant_id = tenant_id or data.get("tenant_id")
            except JWTError:
                pass
    return tenant_id, user_id


def build_log_record(
    *,
    request_id: str,
    method: str,
    path: str,
    status: int,
    latency_ms: float,
    tenant_id: str | None,
    user_id: str | None,
    error_code: str | None = None,
    event: str = "http_request",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "event": event,
        "request_id": request_id,
        "method": (method or "GET").upper(),
        "path": path,
        "status": int(status),
        "latency_ms": round(float(latency_ms), 3),
        "tenant_id": tenant_id,
        "user_id": user_id,
    }
    if error_code:
        record["error_code"] = error_code
    return record


def emit_request_log(record: dict[str, Any]) -> None:
    """Emit one JSON log line (stdlib logger; shippable to any aggregator)."""
    line = json.dumps(record, separators=(",", ":"), default=str)
    status = int(record.get("status") or 0)
    if status >= 500:
        logger.error(line)
    elif status >= 400:
        logger.warning(line)
    else:
        logger.info(line)


def should_skip_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path.startswith(p) for p in _SKIP_PATH_PREFIXES)


def safe_error_code_from_body(*, status_code: int, body: bytes | None) -> str | None:
    """Extract safe error code from a response body buffer."""
    if status_code < 400:
        return None
    if body:
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            payload = None
        if isinstance(payload, dict):
            for key in ("detail", "code", "message"):
                code = _safe_error_code_from_detail(payload.get(key))
                if code:
                    return code
            nested = payload.get("data")
            if isinstance(nested, dict):
                code = _safe_error_code_from_detail(nested.get("code") or nested.get("detail"))
                if code:
                    return code
    return safe_error_code(status_code=status_code, response=None)


class RequestLoggingMiddleware:
    """Structured JSON access/error logs + X-Request-ID (Stage 18 L1).

    Pure ASGI middleware so response bodies remain readable for safe error codes
    (BaseHTTPMiddleware can obscure JSONResponse bodies).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not request_log_enabled():
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if request.method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(request)
        scope.setdefault("state", {})
        # Starlette Request.state is backed by scope["state"]
        request.state.request_id = request_id
        path = request.url.path
        skip = should_skip_path(path)
        tenant_id, user_id = peek_auth_context(request)
        start = time.perf_counter()
        status_code = 500
        body_chunks: list[bytes] = []

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                headers = list(message.get("headers") or [])
                # Inject X-Request-ID if absent
                lower = {k.decode("latin-1").lower() for k, _ in headers}
                if REQUEST_ID_HEADER.lower() not in lower:
                    headers.append(
                        (REQUEST_ID_HEADER.lower().encode("latin-1"), request_id.encode("latin-1"))
                    )
                message = {**message, "headers": headers}
            elif message["type"] == "http.response.body":
                chunk = message.get("body") or b""
                if chunk and status_code >= 400 and len(b"".join(body_chunks)) < 8192:
                    body_chunks.append(chunk)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            latency_ms = (time.perf_counter() - start) * 1000.0
            if not skip:
                emit_request_log(
                    build_log_record(
                        request_id=request_id,
                        method=request.method,
                        path=path,
                        status=500,
                        latency_ms=latency_ms,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        error_code="INTERNAL_ERROR",
                        event="http_error",
                    )
                )
            raise

        if skip:
            return

        latency_ms = (time.perf_counter() - start) * 1000.0
        error_code = safe_error_code_from_body(
            status_code=status_code, body=b"".join(body_chunks) if body_chunks else None
        )
        emit_request_log(
            build_log_record(
                request_id=request_id,
                method=request.method,
                path=path,
                status=status_code,
                latency_ms=latency_ms,
                tenant_id=tenant_id,
                user_id=user_id,
                error_code=error_code,
                event="http_error" if status_code >= 400 else "http_request",
            )
        )
