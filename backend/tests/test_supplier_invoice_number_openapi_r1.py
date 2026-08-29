"""supplier_invoice_number ∈ SupplierInvoiceNumberValue OpenAPI (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    AiDocumentPurchaseInvoiceCreate,
    PurchaseInvoiceCreate,
    PurchaseInvoiceUpdate,
    SupplierInvoiceNumberValue,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_num = TypeAdapter(SupplierInvoiceNumberValue)


def test_supplier_invoice_number_value_schema():
    assert _num.validate_python("  SUP-99  ") == "SUP-99"
    for bad in ("", " ", "!!!", "http://evil", "@@", "a" * 101):
        with pytest.raises(ValidationError):
            _num.validate_python(bad)

    ok = PurchaseInvoiceCreate.model_validate(
        {"supplier_invoice_number": "  INV-7788  ", "items": []}
    )
    assert ok.supplier_invoice_number == "INV-7788"
    omit = PurchaseInvoiceCreate.model_validate({"items": []})
    assert omit.supplier_invoice_number is None
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate({"supplier_invoice_number": "!!!"})
    with pytest.raises(ValidationError):
        PurchaseInvoiceCreate.model_validate({"supplier_invoice_number": ""})

    patch_ok = PurchaseInvoiceUpdate.model_validate(
        {"supplier_invoice_number": " OCR-1 "}
    )
    assert patch_ok.supplier_invoice_number == "OCR-1"
    with pytest.raises(ValidationError):
        PurchaseInvoiceUpdate.model_validate({"supplier_invoice_number": "http://x"})

    with pytest.raises(ValidationError):
        AiDocumentPurchaseInvoiceCreate.model_validate(
            {"purchase_order_id": "po1", "supplier_invoice_number": "!!!"}
        )


def test_supplier_invoice_number_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert page.count('aria-label="Supplier invoice number"') >= 3
    assert "supplierInvoiceNo.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Supplier invoice number OpenAPI" in agents
    assert "SupplierInvoiceNumberValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SupplierInvoiceNumberValue" in docs
    assert "Supplier invoice number" in docs


@pytest.mark.asyncio
async def test_supplier_invoice_number_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "name": f"TIP214 Vendor {suffix}",
            "kind": "supplier",
            "email": f"tip214-{suffix}@example.com",
        },
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]
    product_id = seed["p1"].id
    item = {
        "product_id": product_id,
        "quantity": 1,
        "unit_price": 12.5,
        "tax_rate": 0,
    }

    for bad in ("!!!", "", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/purchasing/invoices",
            headers=headers,
            json={
                "supplier_id": supplier_id,
                "supplier_invoice_number": bad,
                "items": [item],
            },
        )
        assert r.status_code == 422, (bad, r.text)

    hello = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "supplier_invoice_number": f"  SupplierInvoiceNumberValue-{suffix}  ",
            "items": [item],
        },
    )
    assert hello.status_code == 200, hello.text
    data = hello.json()["data"]
    assert data["supplier_invoice_number"] == f"SupplierInvoiceNumberValue-{suffix}"
    invoice_id = data["id"]

    patch_bad = await ac.patch(
        f"/api/v1/purchasing/invoices/{invoice_id}",
        headers=headers,
        json={"supplier_invoice_number": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    patch_ok = await ac.patch(
        f"/api/v1/purchasing/invoices/{invoice_id}",
        headers=headers,
        json={"supplier_invoice_number": f"PATCH-{suffix}"},
    )
    assert patch_ok.status_code == 200, patch_ok.text
    assert patch_ok.json()["data"]["supplier_invoice_number"] == f"PATCH-{suffix}"
