"""ProductCreate / Update + variant sku ∈ ProductSkuValue OpenAPI (BR-5.1)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas import (
    ProductCreate,
    ProductSkuValue,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantUpdate,
)
from tests.conftest import auth_headers

ROOT = Path(__file__).resolve().parents[2]
_sku = TypeAdapter(ProductSkuValue)


def test_product_sku_value_schema():
    assert _sku.validate_python("  tip-232.a_1  ") == "TIP-232.A_1"
    for bad in ("", " ", "!!!", "a b", "http://evil", "-SKU", "_X", "."):
        with pytest.raises(ValidationError):
            _sku.validate_python(bad)

    omit = ProductCreate.model_validate({"name": "Widget"})
    assert omit.sku is None
    ok = ProductCreate.model_validate({"name": "Widget", "sku": "  sku-ok-1  "})
    assert ok.sku == "SKU-OK-1"
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "Widget", "sku": ""})
    with pytest.raises(ValidationError):
        ProductCreate.model_validate({"name": "Widget", "sku": "!!!"})

    patch_ok = ProductUpdate.model_validate({"sku": "  beta-9  "})
    assert patch_ok.sku == "BETA-9"
    with pytest.raises(ValidationError):
        ProductUpdate.model_validate({"sku": "a b"})

    v_ok = ProductVariantCreate.model_validate({"name": "Large", "sku": " var-1 "})
    assert v_ok.sku == "VAR-1"
    with pytest.raises(ValidationError):
        ProductVariantUpdate.model_validate({"sku": ""})


def test_product_sku_ui_and_docs():
    page = (ROOT / "frontend/app/inventory/page.tsx").read_text(encoding="utf-8")
    assert 'aria-label="Product SKU"' in page
    assert 'aria-label="Variant SKU"' in page
    assert "sku: productSku.trim() || null" in page
    assert "sku: variantSku.trim() || null" in page
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Product SKU OpenAPI" in agents
    assert "ProductSkuValue" in agents
    docs = (ROOT / "docs/API_DOCUMENTATION.md").read_text(encoding="utf-8")
    assert "ProductSkuValue" in docs
    assert "Product SKU" in docs
    assert "Variant SKU" in docs


@pytest.mark.asyncio
async def test_product_sku_api_blank_invalid_422(client):
    ac, _seed = client
    headers = await auth_headers(ac, email="admin@alpha.example.com", tenant_slug="alpha")
    suffix = uuid4().hex[:8]

    for bad in ("!!!", "", "a b", "http://evil.example/p"):
        r = await ac.post(
            "/api/v1/products",
            headers=headers,
            json={"name": f"TIP232 Product {suffix}", "sku": bad, "selling_price": 1},
        )
        assert r.status_code == 422, (bad, r.text)

    omit = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={"name": f"TIP232 Auto {suffix}", "selling_price": 1},
    )
    assert omit.status_code == 200, omit.text
    assert omit.json()["data"]["sku"].startswith("SKU-")

    hello = await ac.post(
        "/api/v1/products",
        headers=headers,
        json={
            "name": f"TIP232 Explicit {suffix}",
            "sku": f"  tip232-{suffix}  ",
            "selling_price": 2,
        },
    )
    assert hello.status_code == 200, hello.text
    assert hello.json()["data"]["sku"] == f"TIP232-{suffix}".upper()
    product_id = hello.json()["data"]["id"]

    patch_bad = await ac.patch(
        f"/api/v1/products/{product_id}",
        headers=headers,
        json={"sku": "!!!"},
    )
    assert patch_bad.status_code == 422, patch_bad.text

    variant_bad = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": f"TIP232 Var {suffix}", "sku": ""},
    )
    assert variant_bad.status_code == 422, variant_bad.text

    variant_ok = await ac.post(
        f"/api/v1/products/{product_id}/variants",
        headers=headers,
        json={"name": f"TIP232 Var OK {suffix}", "sku": f"  tip232v-{suffix}  "},
    )
    assert variant_ok.status_code == 200, variant_ok.text
    assert variant_ok.json()["data"]["sku"] == f"TIP232V-{suffix}".upper()
