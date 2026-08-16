"""GET /reports/inventory/stock-counts status Query OpenAPI Literal (BR-5.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import StockCountReportStatusValue
from app.stock_counts import COUNT_STATUSES
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_stock_count_report_status_literal_covers_valid():
    lit = StockCountReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(COUNT_STATUSES)


def test_stock_count_report_status_literal_schema():
    adapter = TypeAdapter(StockCountReportStatusValue)
    assert adapter.validate_python("completed") == "completed"
    assert adapter.validate_python("  Draft ") == "draft"
    assert adapter.validate_python("CANCELLED") == "cancelled"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_stock_count_report_status_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'value="completed"' in page
    assert 'value="draft"' in page
    assert 'value="cancelled"' in page
    assert "Count status" in page
    assert "stockCountStatus" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Stock count report status OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "stock-counts" in docs
    assert "422" in docs
    assert "Count status" in docs


@pytest.mark.asyncio
async def test_stock_count_report_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/inventory/stock-counts?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/reports/inventory/stock-counts?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    ok = await ac.get(
        "/api/v1/reports/inventory/stock-counts?status=Completed",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert "count_sessions" in ok.json()["data"] or "counts" in ok.json()["data"]

    omit = await ac.get("/api/v1/reports/inventory/stock-counts", headers=headers)
    assert omit.status_code == 200, omit.text
