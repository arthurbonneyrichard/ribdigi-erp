"""GET sales/purchasing returns manage status Query OpenAPI + FE filters."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.reports import RETURN_REPORT_STATUSES
from app.schemas import ReturnReportStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_return_manage_status_reuses_report_literal():
    lit = ReturnReportStatusValue.__args__[0]
    assert set(lit.__args__) == set(RETURN_REPORT_STATUSES)
    adapter = TypeAdapter(ReturnReportStatusValue)
    assert adapter.validate_python("  Posted ") == "posted"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("received")


def test_return_manage_status_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "returnManageFilter" in sales
    assert "managedReturns" in sales
    assert 'aria-label="Sales return status filter"' in sales
    assert "No sales returns for this filter" in sales
    assert "returnManageFilter" in purchasing
    assert "managedReturns" in purchasing
    assert 'aria-label="Purchase return status filter"' in purchasing
    assert "No purchase returns for this filter" in purchasing
    for page in (sales, purchasing):
        assert 'value="draft"' in page
        assert 'value="posted"' in page
        assert 'value="cancelled"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Return manage status Query OpenAPI" in agents
    assert "returnManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "returnManageFilter" in docs
    assert "GET /sales/returns" in docs
    assert "GET /purchasing/returns" in docs


@pytest.mark.asyncio
async def test_return_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    for path in ("/api/v1/sales/returns", "/api/v1/purchasing/returns"):
        blank = await ac.get(f"{path}?status=", headers=headers)
        assert blank.status_code == 422, blank.text

        bad = await ac.get(f"{path}?status=received", headers=headers)
        assert bad.status_code == 422, bad.text

    inv = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 20}],
        },
    )
    assert inv.status_code == 200, inv.text
    iid = inv.json()["data"]["id"]
    posted = await ac.post(f"/api/v1/sales/invoices/{iid}/post", headers=headers)
    assert posted.status_code == 200, posted.text

    created = await ac.post(
        "/api/v1/sales/returns",
        headers=headers,
        json={
            "sales_invoice_id": iid,
            "reason": "damaged",
            "restock": False,
            "items": [
                {"product_id": seed["p1"].id, "quantity": 1, "condition": "discard"}
            ],
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/sales/returns?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == rid for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    cancelled = await ac.get("/api/v1/sales/returns?status=cancelled", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert all(r["status"] == "cancelled" for r in cancelled.json()["data"])
    assert not any(r["id"] == rid for r in cancelled.json()["data"])

    omit = await ac.get("/api/v1/sales/returns", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == rid for r in omit.json()["data"])

    # Purchasing list: coerce + omit still 200 (filter honesty on empty tenant list)
    ok = await ac.get("/api/v1/purchasing/returns?status=Posted", headers=headers)
    assert ok.status_code == 200, ok.text
    assert all(r["status"] == "posted" for r in ok.json()["data"])
