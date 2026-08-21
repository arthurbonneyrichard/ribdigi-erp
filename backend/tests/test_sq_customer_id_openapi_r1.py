"""SalesQuotationCreate.customer_id ∈ UuidIdValue OpenAPI honesty (BR-7.2)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import SalesQuotationCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
_ITEMS = [{"product_id": "11111111-2222-3333-4444-555555555555", "quantity": 1, "unit_price": 10}]


def test_sq_customer_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = SalesQuotationCreate.model_validate(
        {"customer_id": f"  {_VALID}  ", "items": _ITEMS}
    )
    assert ok.customer_id == _VALID.lower()
    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        with pytest.raises(ValidationError):
            SalesQuotationCreate.model_validate({"customer_id": bad, "items": _ITEMS})
    with pytest.raises(ValidationError):
        SalesQuotationCreate.model_validate({"items": _ITEMS})


def test_sq_customer_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sale customer"' in page
    assert "customer_id: customerId.trim()" in page
    assert 'aria-label="Create quotation"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Sales quotation customer_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /sales/quotations" in docs
    assert "Sale customer" in docs


@pytest.mark.asyncio
async def test_sq_customer_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    item = {"product_id": seed["p1"].id, "quantity": 1, "unit_price": 8}
    cust = seed["party1"].id

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "cust_001"):
        resp = await ac.post(
            "/api/v1/sales/quotations",
            headers=headers,
            json={"customer_id": bad, "items": [item]},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={"customer_id": f"  {str(cust).upper()}  ", "items": [item]},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["customer_id"] == str(cust).lower()

    missing = await ac.post(
        "/api/v1/sales/quotations",
        headers=headers,
        json={"customer_id": str(uuid4()), "items": [item]},
    )
    assert missing.status_code in (400, 404), missing.text
