"""GET /purchasing/invoices status Query OpenAPI + Purchasing Invoices filter (BR-6.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.purchasing import PI_MANAGE_STATUSES
from app.schemas import PurchaseInvoiceStatusValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_pi_manage_status_literal_covers_lifecycle():
    lit = PurchaseInvoiceStatusValue.__args__[0]
    assert set(lit.__args__) == set(PI_MANAGE_STATUSES)
    adapter = TypeAdapter(PurchaseInvoiceStatusValue)
    assert adapter.validate_python("  Draft ") == "draft"
    assert adapter.validate_python("Overdue") == "overdue"
    with pytest.raises(ValidationError):
        adapter.validate_python("")
    with pytest.raises(ValidationError):
        adapter.validate_python("posted")


def test_pi_manage_status_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert "piManageFilter" in page
    assert "managedInvoices" in page
    assert 'aria-label="Purchase invoice status filter"' in page
    for value in ("draft", "unpaid", "partial", "paid", "overdue", "cancelled"):
        assert f'value="{value}"' in page
    assert "No purchase invoices for this filter" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PI manage status Query OpenAPI" in agents
    assert "piManageFilter" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "piManageFilter" in docs
    assert "GET /purchasing/invoices" in docs
    assert "`draft`|`unpaid`|`partial`|`paid`|`overdue`|`cancelled`" in docs


@pytest.mark.asyncio
async def test_pi_manage_status_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    mgr = await auth_headers(ac, email="mgr@alpha.example.com", tenant_slug="alpha")

    blank = await ac.get("/api/v1/purchasing/invoices?status=", headers=mgr)
    assert blank.status_code == 422, blank.text

    bad = await ac.get("/api/v1/purchasing/invoices?status=posted", headers=mgr)
    assert bad.status_code == 422, bad.text

    for status in sorted(PI_MANAGE_STATUSES):
        ok = await ac.get(f"/api/v1/purchasing/invoices?status={status}", headers=mgr)
        assert ok.status_code == 200, ok.text
        assert all(row["status"] == status for row in ok.json()["data"])

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": "PI Manage Status Vendor",
            "kind": "supplier",
            "email": "pi-manage-status@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text

    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 12,
                    "tax_rate": 0,
                }
            ],
            "notes": "piManageFilter hello-world",
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["status"] == "draft"
    inv_id = inv["id"]

    draft = await ac.get("/api/v1/purchasing/invoices?status=Draft", headers=mgr)
    assert draft.status_code == 200, draft.text
    assert any(row["id"] == inv_id for row in draft.json()["data"])
    assert all(row["status"] == "draft" for row in draft.json()["data"])

    cancelled = await ac.get("/api/v1/purchasing/invoices?status=cancelled", headers=mgr)
    assert cancelled.status_code == 200, cancelled.text
    assert all(row["id"] != inv_id for row in cancelled.json()["data"])
    assert all(row["status"] == "cancelled" for row in cancelled.json()["data"])

    omit = await ac.get("/api/v1/purchasing/invoices", headers=mgr)
    assert omit.status_code == 200, omit.text
    assert any(row["id"] == inv_id for row in omit.json()["data"])
