"""PurchaseInvoiceCancel.reason OpenAPI honesty (BR-6.5)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import PurchaseInvoiceCancel
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_purchase_invoice_cancel_reason_schema():
    ok = PurchaseInvoiceCancel.model_validate({"reason": "  Duplicate invoice  "})
    assert ok.reason == "Duplicate invoice"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            PurchaseInvoiceCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        PurchaseInvoiceCancel.model_validate({})


def test_purchase_invoice_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Purchase invoice cancel reason"' in page
    assert "piCancelReason" in page
    assert "aria-label={`Cancel purchase invoice ${inv.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "PurchaseInvoiceCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "PurchaseInvoiceCancelReasonValue" in docs


@pytest.mark.asyncio
async def test_purchase_invoice_cancel_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP200 cancel {suffix}"

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"TIP200 Vendor {suffix}", "kind": "supplier"},
    )
    assert supplier.status_code == 200, supplier.text
    created = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={
            "supplier_id": supplier.json()["data"]["id"],
            "notes": f"tip200 {suffix}",
            "items": [
                {
                    "product_id": seed["p1"].id,
                    "quantity": 1,
                    "unit_price": 9,
                    "tax_rate": 0,
                }
            ],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/purchasing/invoices/{inv_id}/cancel",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/purchasing/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert f"Cancel: {tag}" in (body.get("notes") or "")
