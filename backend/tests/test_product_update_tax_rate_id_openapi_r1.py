"""ProductUpdate.tax_rate_id ∈ UuidIdValue OpenAPI honesty (BR-5.1 / BR-12.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductUpdate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_product_update_tax_rate_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ProductUpdate.model_validate({})
    assert omit.tax_rate_id is None
    ok = ProductUpdate.model_validate({"tax_rate_id": f"  {_VALID}  "})
    assert ok.tax_rate_id == _VALID.lower()
    nullish = ProductUpdate.model_validate({"tax_rate_id": None})
    assert nullish.tax_rate_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "tax_001", "a b"):
        with pytest.raises(ValidationError):
            ProductUpdate.model_validate({"tax_rate_id": bad})


def test_product_update_tax_rate_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Edit product tax rate"' in page
    assert "tax_rate_id: editTaxRateId.trim() || null" in page
    assert 'aria-label="Save product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product update tax_rate_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit product tax rate" in docs
    assert "PATCH /products/{product_id}" in docs


@pytest.mark.asyncio
async def test_product_update_tax_rate_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Tip321 product {suffix}"},
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "tax_001"):
        resp = await ac.patch(
            f"/api/v1/products/{product_id}",
            headers=headers,
            json={"tax_rate_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"description": f"Tip321 omit tax rate {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    rate = await ac.post(
        "/api/v1/tax/rates",
        headers=headers,
        json={"name": f"Tip321 VAT {suffix}", "rate": 7.5, "tax_type": "vat"},
    )
    assert rate.status_code == 200, rate.text
    rate_id = rate.json()["data"]["id"]

    ok = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"tax_rate_id": f"  {str(rate_id).upper()}  "},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["tax_rate_id"] == str(rate_id).lower()
