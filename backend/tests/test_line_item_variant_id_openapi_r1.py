"""LineItem / SalesInvoiceItemCreate.variant_id ∈ UuidIdValue OpenAPI honesty (BR-7.4 / BR-8.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import LineItem, SalesInvoiceItemCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "11111111-2222-3333-4444-555555555555"
_PRODUCT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def test_line_item_variant_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    ok = LineItem.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "variant_id": f"  {_VALID}  "}
    )
    assert ok.variant_id == _VALID.lower()
    omit_ok = LineItem.model_validate({"product_id": _PRODUCT, "quantity": 1})
    assert omit_ok.variant_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "var_001", "a b"):
        with pytest.raises(ValidationError):
            LineItem.model_validate(
                {"product_id": _PRODUCT, "quantity": 1, "variant_id": bad}
            )
    si = SalesInvoiceItemCreate.model_validate(
        {"product_id": _PRODUCT, "quantity": 1, "variant_id": _VALID}
    )
    assert si.variant_id == _VALID.lower()
    with pytest.raises(ValidationError):
        SalesInvoiceItemCreate.model_validate(
            {"product_id": _PRODUCT, "quantity": 1, "variant_id": "!!!"}
        )


def test_line_item_variant_id_ui_and_docs():
    page = (ROOT / "frontend/app/sales/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Sales variant"' in page
    assert "variant_id: variantId.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Line item variant_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Sales variant" in docs
    assert "variant_id" in docs


@pytest.mark.asyncio
async def test_line_item_variant_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    product_id = seed["p1"].id
    suffix = uuid4().hex[:8]

    customer = await ac.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": f"TIP368 Customer {suffix}"},
    )
    assert customer.status_code == 200, customer.text
    customer_id = customer.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "var_001"):
        resp = await ac.post(
            "/api/v1/sales/invoices",
            headers=headers,
            json={
                "customer_id": customer_id,
                "items": [
                    {
                        "product_id": product_id,
                        "quantity": 1,
                        "unit_price": 1,
                        "variant_id": bad,
                    }
                ],
            },
        )
        assert resp.status_code == 422, (bad, resp.text)

    missing = await ac.post(
        "/api/v1/sales/invoices",
        headers=headers,
        json={
            "customer_id": customer_id,
            "items": [
                {
                    "product_id": product_id,
                    "quantity": 1,
                    "unit_price": 1,
                    "variant_id": f"  {str(uuid4()).upper()}  ",
                }
            ],
        },
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
