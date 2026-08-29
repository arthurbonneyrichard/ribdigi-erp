"""GET /sales/orders status Query OpenAPI + Sales Orders filter (BR-7.3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.sales_docs import SO_MANAGE_STATUSES
from app.schemas import SalesOrderStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_so_manage_status_literal_covers_lifecycle():
    lit = SalesOrderStatusValue.__args__[0]
    assert set(lit.__args__) == set(SO_MANAGE_STATUSES)
    adapter = TypeAdapter(SalesOrderStatusValue)
    assert adapter.validate_python("  Confirmed ") == "confirmed"
    assert adapter.validate_python("Invoiced") == "invoiced"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("open")


def test_so_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert "orderManageFilter" in page
    assert "managedOrders" in page
    assert 'aria-label="Sales order status filter"' in page
    for value in (
        "draft",
        "confirmed",
        "processing",
        "shipped",
        "delivered",
        "invoiced",
        "cancelled",
    ):
        assert f'value="{value}"' in page
    assert "No sales orders for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales order manage status Query OpenAPI" in agents
    assert "orderManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "orderManageFilter" in docs
    assert "GET /sales/orders" in docs


@pytest.mark.asyncio
async def test_so_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/sales/orders?status=", headers=headers)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/sales/orders?status=open", headers=headers)
    assert bad.status_code == 422, bad.text

    for status in sorted(SO_MANAGE_STATUSES):
        ok = await ac.get(f"/api/v1/sales/orders?status={status}", headers=headers)
        assert ok.status_code == 200, ok.text
        assert all(r["status"] == status for r in ok.json()["data"])

    created = await ac.post(
        "/api/v1/sales/orders",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "notes": "orderManageFilter hello-world",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 10}],
        },
    )
    assert created.status_code == 200, created.text
    oid = created.json()["data"]["id"]
    assert created.json()["data"]["status"] == "draft"

    draft = await ac.get("/api/v1/sales/orders?status=Draft", headers=headers)
    assert draft.status_code == 200, draft.text
    rows = draft.json()["data"]
    assert any(r["id"] == oid for r in rows)
    assert all(r["status"] == "draft" for r in rows)

    cancelled = await ac.get("/api/v1/sales/orders?status=cancelled", headers=headers)
    assert cancelled.status_code == 200, cancelled.text
    assert all(r["status"] == "cancelled" for r in cancelled.json()["data"])
    assert not any(r["id"] == oid for r in cancelled.json()["data"])

    omit = await ac.get("/api/v1/sales/orders", headers=headers)
    assert omit.status_code == 200, omit.text
    assert any(r["id"] == oid for r in omit.json()["data"])
