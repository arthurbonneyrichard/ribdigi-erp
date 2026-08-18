"""PurchaseInvoiceUpdate.invoice_date / due_date OpenAPI honesty."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseInvoiceUpdate
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_invoice_date_schema():
    omit = PurchaseInvoiceUpdate.model_validate({})
    assert omit.invoice_date is None
    assert omit.due_date is None
    ok = PurchaseInvoiceUpdate.model_validate(
        {"invoice_date": " 2026-08-01 ", "due_date": "2026-09-15T12:00:00"}
    )
    assert ok.invoice_date == "2026-08-01"
    assert ok.due_date == "2026-09-15T12:00:00"
    for bad in ("", " ", "not-a-date", "01/02/2024", "2026-13-01"):
        with pytest.raises(ValidationError):
            PurchaseInvoiceUpdate.model_validate({"invoice_date": bad})
        with pytest.raises(ValidationError):
            PurchaseInvoiceUpdate.model_validate({"due_date": bad})


def test_purchase_invoice_date_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase invoice OCR date"' in page
    assert "invoiceDate.trim()" in page or "ocrDraft.invoice_date.trim()" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Purchase invoice date OpenAPI" in agents
    assert "IsoDateQueryValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Purchase invoice OCR date" in docs
    assert "PATCH /purchasing/invoices/{invoice_id}" in docs
    assert "IsoDateQueryValue" in docs


@pytest.mark.asyncio
async def test_purchase_invoice_date_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"PI Date Vendor {uuid4().hex[:6]}",
            "kind": "supplier",
            "email": f"pi-date-{uuid4().hex[:6]}@example.com",
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
            "notes": "purchase invoice date OpenAPI hello-world",
        },
    )
    assert created.status_code == 200, created.text
    inv = created.json()["data"]
    assert inv["status"] == "draft"
    inv_id = inv["id"]

    for field in ("invoice_date", "due_date"):
        for bad in ("", "not-a-date", "01/02/2024"):
            resp = await ac.patch(
                f"/api/v1/purchasing/invoices/{inv_id}",
                headers=headers,
                json={field: bad},
            )
            assert resp.status_code == 422, (field, bad, resp.text)

    ok = await ac.patch(
        f"/api/v1/purchasing/invoices/{inv_id}",
        headers=headers,
        json={"invoice_date": "2026-08-01", "due_date": "2026-09-15"},
    )
    assert ok.status_code == 200, ok.text
    data = ok.json()["data"]
    assert str(data["invoice_date"]).startswith("2026-08-01")
    assert str(data["due_date"]).startswith("2026-09-15")

    omit = await ac.patch(
        f"/api/v1/purchasing/invoices/{inv_id}",
        headers=headers,
        json={"notes": "date fields omitted — no change"},
    )
    assert omit.status_code == 200, omit.text
    kept = omit.json()["data"]
    assert str(kept["invoice_date"]).startswith("2026-08-01")
    assert str(kept["due_date"]).startswith("2026-09-15")
