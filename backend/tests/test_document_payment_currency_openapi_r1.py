"""Document/payment create currency ISO OpenAPI honesty (BR-2.6)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    CustomerPaymentCreate,
    PurchaseInvoiceCreate,
    SalesInvoiceCreate,
    SupplierPaymentCreate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]


def test_document_payment_currency_schema():
    si = SalesInvoiceCreate.model_validate(
        {
            "customer_id": "c1",
            "items": [{"product_id": "p1", "quantity": 1}],
            "currency": " usd ",
        }
    )
    assert si.currency == "USD"

    pi = PurchaseInvoiceCreate.model_validate({"currency": "eur"})
    assert pi.currency == "EUR"

    cp = CustomerPaymentCreate.model_validate(
        {"customer_id": "c1", "amount": 10, "currency": None}
    )
    assert cp.currency is None

    sp = SupplierPaymentCreate.model_validate(
        {"supplier_id": "s1", "amount": 10, "currency": "ghs"}
    )
    assert sp.currency == "GHS"

    for Cls, base in (
        (
            SalesInvoiceCreate,
            {"customer_id": "c1", "items": [{"product_id": "p1", "quantity": 1}]},
        ),
        (PurchaseInvoiceCreate, {}),
        (CustomerPaymentCreate, {"customer_id": "c1", "amount": 1}),
        (SupplierPaymentCreate, {"supplier_id": "s1", "amount": 1}),
    ):
        for bad in ("", " ", "US", "EURO", "gh", "123"):
            with pytest.raises(ValidationError):
                Cls.model_validate({**base, "currency": bad})


def test_document_payment_currency_ui_and_docs():
    sales = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales invoice currency"' in sales
    purchasing = (ROOT / "frontend/app/purchasing/page.tsx").read_text(encoding="utf-8")
    assert purchasing.count('aria-label="Purchase invoice currency"') >= 2
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Document/payment currency OpenAPI" in agents
    assert "CurrencyCodeValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert 'aria-label="Sales invoice currency"' in docs
    assert 'aria-label="Purchase invoice currency"' in docs


@pytest.mark.asyncio
async def test_sales_invoice_currency_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    body = {
        "customer_id": seed["party1"].id,
        "items": [{"product_id": seed["p1"].id, "quantity": 1, "unit_price": 1}],
    }

    blank = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={**body, "currency": ""},
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={**body, "currency": "EURO"},
    )
    assert bad.status_code == 422, bad.text

    ok = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={**body, "currency": "ghs", "notes": f"fx-honest-{uuid4().hex[:6]}"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("currency") == "GHS"


@pytest.mark.asyncio
async def test_purchase_invoice_currency_blank_invalid_422(client):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    supplier = await ac.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"name": f"FX Supplier {uuid4().hex[:6]}"},
    )
    assert supplier.status_code == 200, supplier.text
    supplier_id = supplier.json()["data"]["id"]

    body = {
        "supplier_id": supplier_id,
        "items": [
            {
                "product_id": seed["p1"].id,
                "quantity": 1,
                "unit_price": 1,
                "tax_rate": 0,
            }
        ],
    }

    blank = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={**body, "currency": ""},
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={**body, "currency": "EURO"},
    )
    assert bad.status_code == 422, bad.text

    ok = await ac.post(
        "/api/v1/purchasing/invoices",
        headers=headers,
        json={**body, "currency": "ghs"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"].get("currency") == "GHS"


@pytest.mark.asyncio
async def test_customer_payment_currency_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")

    blank = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={"customer_id": "00000000-0000-0000-0000-000000000001", "amount": 1, "currency": ""},
    )
    assert blank.status_code == 422, blank.text

    bad = await ac.post(
        "/api/v1/sales/payments",
        headers=headers,
        json={
            "customer_id": "00000000-0000-0000-0000-000000000001",
            "amount": 1,
            "currency": "EURO",
        },
    )
    assert bad.status_code == 422, bad.text
