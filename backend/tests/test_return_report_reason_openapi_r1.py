"""GET /reports/sales|/purchases/returns reason Query OpenAPI Literals (BR-14.1/14.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.purchasing import PURCHASE_RETURN_REASONS
from app.sales_docs import RETURN_REASONS
from app.schemas import PurchaseReturnReportReasonValue, SalesReturnReportReasonValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_return_report_reason_literal_covers_valid():
    lit = SalesReturnReportReasonValue.__args__[0]
    assert set(lit.__args__) == set(RETURN_REASONS)


def test_purchase_return_report_reason_literal_covers_valid():
    lit = PurchaseReturnReportReasonValue.__args__[0]
    assert set(lit.__args__) == set(PURCHASE_RETURN_REASONS)


def test_sales_return_report_reason_literal_schema():
    adapter = TypeAdapter(SalesReturnReportReasonValue)
    assert adapter.validate_python("damaged") == "damaged"
    assert adapter.validate_python("  Wrong_Item ") == "wrong_item"
    assert adapter.validate_python("CUSTOMER_CHANGE") == "customer_change"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("expiry")
    with pytest.raises(ValidationError):
        adapter.validate_python("not-a-reason")


def test_purchase_return_report_reason_literal_schema():
    adapter = TypeAdapter(PurchaseReturnReportReasonValue)
    assert adapter.validate_python("quality") == "quality"
    assert adapter.validate_python("  Expiry ") == "expiry"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("defective")
    with pytest.raises(ValidationError):
        adapter.validate_python("not-a-reason")


def test_return_report_reason_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "salesReturnReason" in page
    assert "purchaseReturnReason" in page
    assert 'aria-label="Sales return reason"' in page
    assert 'aria-label="Purchase return reason"' in page
    assert 'value="customer_change"' in page
    assert 'value="quality"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Return report reason OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Return reason" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_sales_return_report_reason_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/sales/returns?reason=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/reports/sales/returns?reason=not-a-reason", headers=headers)
    assert bad.status_code == 422, bad.text

    # purchase-only reason must not be accepted on sales
    cross = await ac.get("/api/v1/reports/sales/returns?reason=expiry", headers=headers)
    assert cross.status_code == 422, cross.text

    ok = await ac.get("/api/v1/reports/sales/returns?reason=Damaged", headers=headers)
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert all(r["reason"] == "damaged" for r in body["returns"])

    omit = await ac.get("/api/v1/reports/sales/returns", headers=headers)
    assert omit.status_code == 200, omit.text


@pytest.mark.asyncio
async def test_purchase_return_report_reason_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/purchases/returns?reason=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get(
        "/api/v1/reports/purchases/returns?reason=not-a-reason",
        headers=headers,
    )
    assert bad.status_code == 422, bad.text

    cross = await ac.get(
        "/api/v1/reports/purchases/returns?reason=defective",
        headers=headers,
    )
    assert cross.status_code == 422, cross.text

    ok = await ac.get("/api/v1/reports/purchases/returns?reason=Quality", headers=headers)
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert all(r["reason"] == "quality" for r in body["returns"])

    omit = await ac.get("/api/v1/reports/purchases/returns", headers=headers)
    assert omit.status_code == 200, omit.text
