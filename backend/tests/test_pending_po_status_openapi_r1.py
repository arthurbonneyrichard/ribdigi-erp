"""GET /reports/purchases/pending-orders status Query OpenAPI Literal (BR-14.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.reports import PENDING_PO_STATUSES
from app.schemas import PendingPoReportStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pending_po_report_status_literal_covers_valid():
    lit = PendingPoReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(PENDING_PO_STATUSES)


def test_pending_po_report_status_literal_schema():
    adapter = TypeAdapter(PendingPoReportStatusValue)
    assert adapter.validate_python("sent") == "sent"
    assert adapter.validate_python("  Draft ") == "draft"
    assert adapter.validate_python("PARTIALLY_RECEIVED") == "partially_received"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("received")
    with pytest.raises(ValidationError):
        adapter.validate_python("cancelled")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_pending_po_report_status_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'value="partially_received"' in page
    assert 'value="sent"' in page
    assert "Pending status" in page
    assert "pendingPoStatus" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Pending PO report status OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "pending-orders" in docs
    assert "422" in docs
    assert "Pending status" in docs


@pytest.mark.asyncio
async def test_pending_po_report_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/purchases/pending-orders?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get(
        "/api/v1/reports/purchases/pending-orders?status=received",
        headers=headers,
    )
    assert bad.status_code == 422, bad.text

    ok = await ac.get(
        "/api/v1/reports/purchases/pending-orders?status=Sent",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert "orders" in body
    assert all(o["status"] == "sent" for o in body["orders"])

    omit = await ac.get("/api/v1/reports/purchases/pending-orders", headers=headers)
    assert omit.status_code == 200, omit.text
