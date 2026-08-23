"""ProductCreate.brand_id ∈ UuidIdValue OpenAPI honesty (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyotp
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import ProductCreate, UuidIdValue
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_uuid = TypeAdapter(UuidIdValue)

_VALID = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"


def test_product_create_brand_id_schema():
    assert _uuid.validate_python(f"  {_VALID}  ") == _VALID.lower()
    omit = ProductCreate.model_validate({"name": "Widget"})
    assert omit.brand_id is None
    ok = ProductCreate.model_validate(
        {"name": "Widget", "brand_id": f"  {_VALID}  "}
    )
    assert ok.brand_id == _VALID.lower()
    nullish = ProductCreate.model_validate({"name": "Widget", "brand_id": None})
    assert nullish.brand_id is None
    for bad in ("", " ", "!!!", "http://evil", "not-a-uuid", "brand_001", "a b"):
        with pytest.raises(ValidationError):
            ProductCreate.model_validate({"name": "Widget", "brand_id": bad})


def test_product_create_brand_id_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product brand"' in page
    assert "brand_id: productBrandId.trim() || null" in page
    assert 'aria-label="Create product"' in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product create brand_id OpenAPI" in agents
    assert "UuidIdValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "UuidIdValue" in docs
    assert "POST /products" in docs
    assert "Product brand" in docs


@pytest.mark.asyncio
async def test_product_create_brand_id_api_blank_invalid_422(client, seeded):
    ac, seed = client
    code = pyotp.TOTP(seed["super_totp_secret"]).now()
    headers = await auth_headers(
        ac, email="super@alpha.example.com", tenant_slug="alpha", totp_code=code
    )
    suffix = uuid4().hex[:8]

    brand = await ac.post(
        "/api/v1/catalog/brands",
        headers=headers,
        json={"code": f"B291{suffix[:4]}".upper(), "name": f"Tip291 Brand {suffix}"},
    )
    assert brand.status_code == 200, brand.text
    brand_id = brand.json()["data"]["id"]

    for bad in ("", "!!!", "http://evil", "not-a-uuid", "brand_001"):
        resp = await ac.post(
            "/api/v1/products",
            headers=headers,
            json={"name": f"Tip291 bad brand {suffix}", "brand_id": bad},
        )
        assert resp.status_code == 422, (bad, resp.text)

    ok = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": f"Tip291 with brand {suffix}",
            "brand_id": f"  {str(brand_id).upper()}  ",
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["brand_id"] == str(brand_id).lower()

    missing = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"Tip291 missing brand {suffix}", "brand_id": str(uuid4())},
    )
    assert missing.status_code in (400, 404), missing.text
    assert missing.status_code != 422
