"""GET /reports/sales|/purchases/returns status Query OpenAPI Literal (BR-14.1/14.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.reports import RETURN_REPORT_STATUSES
from app.schemas import ReturnReportStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_return_report_status_literal_covers_valid():
    lit = ReturnReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(RETURN_REPORT_STATUSES)


def test_return_report_status_literal_schema():
    adapter = TypeAdapter(ReturnReportStatusValue)
    assert adapter.validate_python("posted") == "posted"
    assert adapter.validate_python("  Draft ") == "draft"
    assert adapter.validate_python("CANCELLED") == "cancelled"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("received")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_return_report_status_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert "salesReturnStatus" in page
    assert "purchaseReturnStatus" in page
    assert 'aria-label="Sales return status"' in page
    assert 'aria-label="Purchase return status"' in page
    assert "Return status" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Return report status OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "reports/sales/returns" in docs
    assert "reports/purchases/returns" in docs
    assert "Return status" in docs
    assert "422" in docs


@pytest.mark.asyncio
async def test_sales_return_report_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/sales/returns?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/reports/sales/returns?status=received", headers=headers)
    assert bad.status_code == 422, bad.text

    ok = await ac.get("/api/v1/reports/sales/returns?status=Posted", headers=headers)
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert "returns" in body
    assert all(r["status"] == "posted" for r in body["returns"])

    omit = await ac.get("/api/v1/reports/sales/returns", headers=headers)
    assert omit.status_code == 200, omit.text


@pytest.mark.asyncio
async def test_purchase_return_report_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/purchases/returns?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/reports/purchases/returns?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    ok = await ac.get("/api/v1/reports/purchases/returns?status=Draft", headers=headers)
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert "returns" in body
    assert all(r["status"] == "draft" for r in body["returns"])

    omit = await ac.get("/api/v1/reports/purchases/returns", headers=headers)
    assert omit.status_code == 200, omit.text
