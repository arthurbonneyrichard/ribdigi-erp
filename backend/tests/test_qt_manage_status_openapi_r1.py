"""GET /sales/quotations status Query OpenAPI + Sales Quotations filter (BR-7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.sales_docs import QT_MANAGE_STATUSES
from app.schemas import SalesQuotationStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_qt_manage_status_literal_covers_lifecycle():
    lit = SalesQuotationStatusValue.__args__[0]
    assert set(lit.__args__) == set(QT_MANAGE_STATUSES)
    adapter = TypeAdapter(SalesQuotationStatusValue)
    assert adapter.validate_python("  Expired ") == "expired"
    assert adapter.validate_python("Converted") == "converted"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_qt_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "quotationManageFilter" in page
    assert "managedQuotations" in page
    assert 'aria-label="Quotation status filter"' in page
    for value in ("draft", "sent", "accepted", "rejected", "expired", "converted"):
        assert f'value="{value}"' in page
    assert "No quotations for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Quotation manage status Query OpenAPI" in agents
    assert "quotationManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "quotationManageFilter" in docs
    assert "GET /sales/quotations" in docs


@pytest.mark.asyncio
async def test_qt_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/sales/quotations?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/sales/quotations?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    for status in sorted(QT_MANAGE_STATUSES):
        ok = await ac.get(f"/api/v1/sales/quotations?status={status}", headers=headers)
        assert ok.status_code == 200, ok.text
        assert all(r["status"] == status for r in ok.json()["data"])

    created = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "notes": "quotationManageFilter hello-world",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    qid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/sales/quotations?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == qid for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    rejected = await ac.get("/api/v1/sales/quotations?status=rejected", headers=headers)
    assert rejected.status_code == 200, rejected.text
    assert all(r["status"] == "rejected" for r in rejected.json()["data"])
    assert not any(r["id"] == qid for r in rejected.json()["data"])

    omit = await ac.get("/api/v1/sales/quotations", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == qid for r in omit.json()["data"])
