"""SalesInvoiceCreate.store_id ∈ UuidIdValue OpenAPI honesty (BR-7.4)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SalesInvoiceCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [
    {
        "product_id": "11111111-2222-3333-4444-555555555555",
        "quantity": 1,
        "unit_price": 10,
    }
]


def test_sales_invoice_store_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = SalesInvoiceCreate.model_validate(
        {"customer_id": _VALID, "items": _ITEMS}
    )
    assert omit.store_id is None
    ok = SalesInvoiceCreate.model_validate(
        {"customer_id": _VALID, "store_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.store_id == _VALID.lower()
    nullish = SalesInvoiceCreate.model_validate(
        {"customer_id": _VALID, "store_id": None, "items": _ITEMS}
    )
    assert nullish.store_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "st_001", "a b"):
        with pytest.raises(ValidationError):
            SalesInvoiceCreate.model_validate(
                {"customer_id": _VALID, "store_id": bad, "items": _ITEMS}
            )


def test_sales_invoice_store_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sale store"' in page
    assert "store_id: storeId.trim() || null" in page
    assert 'aria-label="Create invoice"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales invoice store_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Sale store" in docs
    assert "POST /sales/invoices" in docs


@pytest.mark.asyncio
async def test_sales_invoice_store_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    cust = seed["party1"].id
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "st_001"):
        resp = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={"customer_id": cust, "store_id": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={"customer_id": cust, "items": [item]},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": cust,
            "store_id": f"  {str(uuid4()).upper()}  ",
            "items": [item],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
