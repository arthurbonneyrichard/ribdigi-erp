"""ProductUpdate.brand_id ∈ UuidIdValue OpenAPI honesty (BR-5.1)."""

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


def test_product_update_brand_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ProductUpdate.model_validate({})
    assert omit.brand_id is None
    ok = ProductUpdate.model_validate({"brand_id": f"  {_VALID}  "})
    assert ok.brand_id == _VALID.lower()
    nullish = ProductUpdate.model_validate({"brand_id": None})
    assert nullish.brand_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "brand_001", "a b"):
        with pytest.raises(ValidationError):
            ProductUpdate.model_validate({"brand_id": bad})


def test_product_update_brand_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Edit product brand"' in page
    assert "brand_id: editBrandId.trim() || null" in page
    assert 'aria-label="Save product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product update brand_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "Edit product brand" in docs
    assert "PATCH /products/{product_id}" in docs


@pytest.mark.asyncio
async def test_product_update_brand_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    created = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Tip319 product {suffix}"},
    )
    assert created.status_code == 200, created.text
    product_id = created.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "brand_001"):
        resp = await ac.patch(
            f"/api/v1/products/{product_id}",
            headers=headers,
            json={"brand_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    omit = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"description": f"Tip319 omit brand {suffix}"},
    )
    assert omit.status_code == 200, omit.text

    missing = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"brand_id": f"  {str(uuid4()).upper()}  "},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
