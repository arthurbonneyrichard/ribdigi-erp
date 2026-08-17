"""GET /reports/inventory/transfers status Query OpenAPI Literal (BR-13.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.reports import TRANSFER_REPORT_STATUSES
from app.schemas import TransferReportStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_transfer_report_status_literal_covers_valid():
    lit = TransferReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(TRANSFER_REPORT_STATUSES)


def test_transfer_report_status_literal_schema():
    adapter = TypeAdapter(TransferReportStatusValue)
    assert adapter.validate_python("received") == "received"
    assert adapter.validate_python("  In_Transit ") == "in_transit"
    assert adapter.validate_python("REQUESTED") == "requested"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("   ")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")
    with pytest.raises(ValidationError):
        adapter.validate_python("garbage_xyz")


def test_transfer_report_status_ui_and_docs():
    page = (ROOT / "frontend/app/reports/page.tsx").read_text(encoding="utf-8")
    assert 'value="received"' in page
    assert 'value="requested"' in page
    assert 'value="in_transit"' in page
    assert "Transfer status" in page
    assert "transferStatus" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Transfer report status OpenAPI" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "inventory/transfers" in docs
    assert "422" in docs
    assert "Transfer status" in docs


@pytest.mark.asyncio
async def test_transfer_report_status_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/reports/inventory/transfers?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/reports/inventory/transfers?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    ok = await ac.get(
        "/api/v1/reports/inventory/transfers?status=Received",
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert "transfers" in body
    assert all(t["status"] == "received" for t in body["transfers"])

    omit = await ac.get("/api/v1/reports/inventory/transfers", headers=headers)
    assert omit.status_code == 200, omit.text
