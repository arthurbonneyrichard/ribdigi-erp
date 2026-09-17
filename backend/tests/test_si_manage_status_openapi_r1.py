"""GET /sales/invoices status Query OpenAPI + Sales Invoices filter (BR-7.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.sales import SI_MANAGE_STATUSES
from app.schemas import SalesInvoiceStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_si_manage_status_literal_covers_lifecycle():
    lit = SalesInvoiceStatusValue.__args__[0]
    assert set(lit.__args__) == set(SI_MANAGE_STATUSES)
    adapter = TypeAdapter(SalesInvoiceStatusValue)
    assert adapter.validate_python("  Overdue ") == "overdue"
    assert adapter.validate_python("Partial") == "partial"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_si_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "invoiceManageFilter" in page
    assert "managedInvoices" in page
    assert 'aria-label="Sales invoice status filter"' in page
    for value in (
        "draft",
        "posted",
        "sent",
        "partial",
        "paid",
        "overdue",
        "cancelled",
    ):
        assert f'value="{value}"' in page
    assert "No sales invoices for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales invoice manage status Query OpenAPI" in agents
    assert "invoiceManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "invoiceManageFilter" in docs
    assert "GET /sales/invoices" in docs


@pytest.mark.asyncio
async def test_si_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/sales/invoices?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/sales/invoices?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    for status in sorted(SI_MANAGE_STATUSES):
        ok = await ac.get(f"/api/v1/sales/invoices?status={status}", headers=headers)
        assert ok.status_code == 200, ok.text
        assert all(r["status"] == status for r in ok.json()["data"])

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 12}],
            "notes": "invoiceManageFilter hello-world",
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/sales/invoices?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == inv_id for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    cancelled = await ac.get("/api/v1/sales/invoices?status=cancelled", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert all(r["status"] == "cancelled" for r in cancelled.json()["data"])
    assert not any(r["id"] == inv_id for r in cancelled.json()["data"])

    omit = await ac.get("/api/v1/sales/invoices", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == inv_id for r in omit.json()["data"])
