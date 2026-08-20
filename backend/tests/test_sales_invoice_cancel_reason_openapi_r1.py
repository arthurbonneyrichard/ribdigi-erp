"""SalesInvoiceCancel.reason OpenAPI honesty (BR-7.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import SalesInvoiceCancel
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_sales_invoice_cancel_reason_schema():
    ok = SalesInvoiceCancel.model_validate({"reason": "  Duplicate invoice  "})
    assert ok.reason == "Duplicate invoice"
    for bad in ("", " ", "!!!", "!!!!", "http://evil", "@@"):
        with pytest.raises(ValidationError):
            SalesInvoiceCancel.model_validate({"reason": bad})
    with pytest.raises(ValidationError):
        SalesInvoiceCancel.model_validate({})


def test_sales_invoice_cancel_reason_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales invoice cancel reason"' in page
    assert "siCancelReason" in page
    assert "aria-label={`Cancel sales invoice ${inv.id}`}" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "SalesInvoiceCancelReasonValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "SalesInvoiceCancelReasonValue" in docs


@pytest.mark.asyncio
async def test_sales_invoice_cancel_reason_api_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]
    tag = f"TIP197 cancel {suffix}"

    created = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": seed["party1"].id,
            "notes": f"tip197 {suffix}",
            "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}],
        },
    )
    assert created.status_code == 200, created.text
    inv_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "   "):
        resp = await ac.post(
            f"/api/v1/sales/invoices/{inv_id}/cancel",
            headers=headers,
            json={"reason": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        f"/api/v1/sales/invoices/{inv_id}/cancel",
        headers=headers,
        json={"reason": tag},
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()["data"]
    assert body["status"] == "cancelled"
    assert f"Cancel: {tag}" in (body.get("notes") or "")
