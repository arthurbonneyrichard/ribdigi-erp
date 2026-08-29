"""GET /purchasing/orders status Query OpenAPI + Purchasing Orders filter (BR-6.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.purchasing import PO_MANAGE_STATUSES
from app.reports import PENDING_PO_STATUSES
from app.schemas import PendingPoReportStatusValue, PurchaseOrderStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_po_manage_status_literal_covers_lifecycle():
    lit = PurchaseOrderStatusValue.__args__[0]
    assert set(lit.__args__) == set(PO_MANAGE_STATUSES)
    assert set(PENDING_PO_STATUSES).issubset(set(PO_MANAGE_STATUSES))
    pending_lit = PendingPoReportStatusValue.__args__[0]
    assert set(pending_lit.__args__) == set(PENDING_PO_STATUSES)
    adapter = TypeAdapter(PurchaseOrderStatusValue)
    assert adapter.validate_python("  Partially_Received ") == "partially_received"
    assert adapter.validate_python("Received") == "received"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_po_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "poManageFilter" in page
    assert "managedOrders" in page
    assert 'aria-label="Purchase order status filter"' in page
    assert 'value="draft"' in page
    assert 'value="sent"' in page
    assert 'value="partially_received"' in page
    assert 'value="received"' in page
    assert 'value="cancelled"' in page
    assert "No purchase orders for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PO manage status Query OpenAPI" in agents
    assert "poManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "poManageFilter" in docs
    assert "GET /purchasing/orders" in docs


@pytest.mark.asyncio
async def test_po_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/purchasing/orders?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/purchasing/orders?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    # Pending-report-only values must still work on manage (superset).
    for status in ("draft", "sent", "partially_received", "received", "cancelled"):
        ok = await ac.get(f"/api/v1/purchasing/orders?status={status}", headers=headers)
        assert ok.status_code == 200, ok.text
        assert all(r["status"] == status for r in ok.json()["data"])

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": "PO Manage Status Supplier", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    created = await ac.post(
        "/api/v1/purchasing/orders",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "items": [{"product_id": seed["p1"].id, "quantity": 2, "unit_price": 5}],
            "notes": "poManageFilter hello-world",
        },
    )
    assert created.status_code == 200, created.text
    po_id = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/purchasing/orders?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == po_id for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    cancelled = await ac.get("/api/v1/purchasing/orders?status=cancelled", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert all(r["status"] == "cancelled" for r in cancelled.json()["data"])
    assert not any(r["id"] == po_id for r in cancelled.json()["data"])

    omit = await ac.get("/api/v1/purchasing/orders", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == po_id for r in omit.json()["data"])
