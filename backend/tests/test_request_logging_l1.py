"""Stage 18 L1: structured request/error logs + health/metrics monitoring hooks."""

from __future__ import annotations

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app import metrics as metrics_svc
from app import request_logging as reqlog
from app.main import app
from app.rate_limit import rate_limiter
from tests.conftest import auth_headers


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _attach_capture() -> tuple[logging.Logger, _ListHandler]:
    handler = _ListHandler()
    logger = logging.getLogger("ribdigi.request")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger, handler


def _detach(logger: logging.Logger, handler: logging.Handler) -> None:
    logger.removeHandler(handler)


def _parsed_logs(handler: _ListHandler) -> list[dict]:
    out: list[dict] = []
    for rec in handler.records:
        try:
            out.append(json.loads(rec.getMessage()))
        except json.JSONDecodeError:
            continue
    return out


def test_request_id_header_and_structured_log_fields():
    rate_limiter.reset_for_tests()
    metrics_svc.reset_for_tests()
    logger, handler = _attach_capture()
    try:
        client = TestClient(app)
        response = client.get(
            "/api/v1/products",
            headers={"X-Request-ID": "s18-l1-req-001"},
        )
        assert response.headers.get("X-Request-ID") == "s18-l1-req-001"
        # Unauthenticated → 401 with structured log
        assert response.status_code == 401
        logs = _parsed_logs(handler)
        assert logs, "expected structured request log"
        hit = next(row for row in logs if row.get("request_id") == "s18-l1-req-001")
        assert hit["event"] == "http_error"
        assert hit["method"] == "GET"
        assert hit["path"] == "/api/v1/products"
        assert hit["status"] == 401
        assert "latency_ms" in hit and float(hit["latency_ms"]) >= 0
        assert hit.get("error_code") in {"UNAUTHENTICATED", "Authentication required"} or (
            isinstance(hit.get("error_code"), str) and hit["error_code"]
        )
        # tenant/user may be null when unauthenticated without JWT
        assert "tenant_id" in hit
        assert "user_id" in hit
    finally:
        _detach(logger, handler)


@pytest.mark.asyncio
async def test_authenticated_log_includes_tenant_and_user(client, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.config.settings.REQUEST_LOG_ENABLED", True)
    monkeypatch.setattr("app.request_logging.settings.REQUEST_LOG_ENABLED", True)

    logger, handler = _attach_capture()
    try:
        headers = await auth_headers(
            ac, email="mgr@alpha.example.com", tenant_slug="alpha"
        )
        rid = "s18-l1-auth-42"
        headers = {**headers, "X-Request-ID": rid}
        response = await ac.get("/api/v1/products", headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers.get("X-Request-ID") == rid

        logs = _parsed_logs(handler)
        hit = next(row for row in logs if row.get("request_id") == rid)
        assert hit["status"] == 200
        assert hit["event"] == "http_request"
        assert hit["tenant_id"] == seed["t1"].id
        assert hit["user_id"] == seed["mgr1"].id
        assert hit.get("error_code") is None
        assert float(hit["latency_ms"]) >= 0
    finally:
        _detach(logger, handler)


@pytest.mark.asyncio
async def test_safe_error_code_for_insufficient_stock(client, db_session, monkeypatch):
    ac, seed = client
    monkeypatch.setattr("app.config.settings.REQUEST_LOG_ENABLED", True)
    monkeypatch.setattr("app.request_logging.settings.REQUEST_LOG_ENABLED", True)

    from app import accounting as accounting_svc

    await accounting_svc.ensure_default_accounts(db_session, seed["t1"].id)
    product = seed["p1"]
    product.stock_qty = 1
    product.reserved_qty = 0
    product.selling_price = 10
    await db_session.commit()

    cashier = await auth_headers(
        ac, email="cashier@alpha.example.com", tenant_slug="alpha"
    )
    opened = await ac.post(
        "/api/v1/pos/sessions/open",
        headers=cashier,
        json={"opening_cash": 20},
    )
    assert opened.status_code == 200, opened.text
    session_id = opened.json()["data"]["session_id"]

    logger, handler = _attach_capture()
    try:
        rid = "s18-l1-stock-fail"
        denied = await ac.post(
            "/api/v1/pos/sales",
            headers={**cashier, "X-Request-ID": rid},
            json={
                "session_id": session_id,
                "payment_method": "cash",
                "items": [{"product_id": product.id, "quantity": 9}],
            },
        )
        assert denied.status_code == 409
        logs = _parsed_logs(handler)
        hit = next(row for row in logs if row.get("request_id") == rid)
        assert hit["status"] == 409
        assert hit["error_code"] == "INSUFFICIENT_STOCK"
        assert hit["event"] == "http_error"
    finally:
        _detach(logger, handler)


@pytest.mark.asyncio
async def test_health_and_metrics_hooks_still_green(client, monkeypatch):
    """MVP monitoring hooks from Stage 5 H5 remain operational under L1."""
    ac, _seed = client
    monkeypatch.setattr("app.config.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.health.settings.CELERY_TASK_ALWAYS_EAGER", True)
    monkeypatch.setattr("app.config.settings.RATE_LIMIT_REQUIRE_REDIS", False)
    monkeypatch.setattr("app.health.settings.RATE_LIMIT_REQUIRE_REDIS", False)

    async def _redis_ok():
        return {"status": "ok", "latency_ms": 0.1}

    monkeypatch.setattr("app.health.check_redis", _redis_ok)

    shallow = await ac.get("/api/v1/health")
    assert shallow.status_code == 200
    assert shallow.json()["data"]["status"] == "ok"

    ready = await ac.get("/api/v1/health/ready")
    assert ready.status_code == 200, ready.text
    assert ready.json()["data"]["deep"] is True
    assert ready.json()["data"]["checks"]["database"]["status"] == "ok"

    metrics = await ac.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "ribdigi_up 1" in metrics.text
    assert "ribdigi_http_requests_total" in metrics.text


def test_health_paths_skipped_from_request_logs():
    rate_limiter.reset_for_tests()
    logger, handler = _attach_capture()
    try:
        client = TestClient(app)
        client.get("/api/v1/health", headers={"X-Request-ID": "skip-health"})
        client.get("/api/v1/metrics", headers={"X-Request-ID": "skip-metrics"})
        logs = _parsed_logs(handler)
        assert not any(row.get("request_id") in {"skip-health", "skip-metrics"} for row in logs)
    finally:
        _detach(logger, handler)


def test_safe_error_code_helpers():
    from starlette.responses import JSONResponse

    assert reqlog.safe_error_code(status_code=200) is None
    assert reqlog.safe_error_code(status_code=429) == "RATE_LIMIT_EXCEEDED"
    assert reqlog.safe_error_code(status_code=503) == "SERVICE_UNAVAILABLE"
    resp = JSONResponse(
        {"detail": {"code": "INSUFFICIENT_STOCK", "available": 1}}, status_code=409
    )
    assert reqlog.safe_error_code(status_code=409, response=resp) == "INSUFFICIENT_STOCK"


def test_ops_monitoring_doc_exists():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    doc = (root / "docs" / "OPS_MONITORING_MVP.md").read_text(encoding="utf-8")
    assert "Stage 18 L1" in doc
    assert "/api/v1/health/ready" in doc
    assert "/api/v1/metrics" in doc
    assert "request_id" in doc
    assert "X-Request-ID" in doc
    assert "Grafana" in doc or "PagerDuty" in doc
